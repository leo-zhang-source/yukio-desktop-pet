#!/usr/bin/env python3
"""Repeat Mac/workbench checks with synthetic data and isolated child settings.

Requires macOS, Swift 6.1+, Python 3.12+ and Node 22+. No Windows work is run.
Exit 0 means the check baseline is stable; documented defects are still defects.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def fingerprint():
    paths = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
    prefixes = ('YukioPlayer/Sources/', 'YukioPlayer/Tests/', 'tools/activity-workbench/', 'tests/remediation/', 'scripts/', 'config/')
    explicit = {'YukioPlayer/Package.swift', 'YukioPlayer/Package.resolved',
                'scripts/run-remediation-checks.py', '.github/workflows/remediation-checks.yml'}
    h = hashlib.sha256()
    for name in sorted(set(paths)):
        if name and (name.startswith(prefixes) or name in explicit):
            path = ROOT / name
            if path.is_file():
                h.update(name.encode() + b'\0' + hashlib.sha256(path.read_bytes()).digest())
    return h.hexdigest()


def run(command, directory, env, log, timeout):
    started = time.monotonic()
    timed_out = False
    with log.open('w', encoding='utf-8') as stream:
        process = subprocess.Popen(command, cwd=directory, env=env, stdout=stream,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            code = 124
    return dict(exit_code=code, timed_out=timed_out, seconds=round(time.monotonic()-started, 2), log=log.name)


def counts(kind, log):
    text = log.read_text(encoding='utf-8', errors='replace')
    patterns = {'swift': r'Test run with (\d+) tests?', 'python': r'Ran (\d+) tests?', 'node': r'# tests (\d+)'}
    matches = re.findall(patterns[kind], text)
    count = int(matches[-1]) if matches else None
    if kind == 'node':
        skipped = re.findall(r'# skipped (\d+)', text)
    elif kind == 'python':
        skipped = re.findall(r'skipped=(\d+)', text)
    else:
        skipped = re.findall(r'Test run.*?with (\d+) tests? skipped', text)
    return dict(tests=count, skipped=int(skipped[-1]) if skipped else 0)


def isolated_environment(out, python, node):
    profile, tmp, binaries = out / 'home', out / 'tmp', out / 'test-bin'
    for directory in [profile, tmp, binaries]: directory.mkdir()
    for name, destination in [('python3', python), ('python', python), ('node', node)]:
        (binaries / name).symlink_to(destination)
    # No inherited model endpoints, API tokens, proxy configuration or client login directories.
    env = {k: os.environ[k] for k in ('DEVELOPER_DIR', 'SDKROOT') if k in os.environ}
    env.update(PATH=str(binaries) + ':/usr/bin:/bin:/usr/sbin:/sbin',
               HOME=str(profile), CFFIXED_USER_HOME=str(profile), TMPDIR=str(tmp) + '/',
               XDG_CONFIG_HOME=str(profile / '.config'), XDG_CACHE_HOME=str(profile / '.cache'),
               LANG='en_US.UTF-8', LC_ALL='en_US.UTF-8', PYTHONUTF8='1', PYTHONIOENCODING='utf-8',
               PYTHONDONTWRITEBYTECODE='1', YUKIO_TEST_PYTHON=python,
               YUKIO_SCENARIO_OBSERVATIONS=str(out / 'mac-observations.json'))
    return env


def negative_controls(out, env, python):
    """Change a real expected assertion, then prove the checker exits nonzero."""
    controls = out / 'negative-controls'
    controls.mkdir()
    fixture = json.loads((ROOT / 'tests/remediation/fixtures/codex-results.json').read_text())
    fixture['cases'][0]['steps'][-1]['expect_events'][0]['kind'] = 'activity_failed'
    write(controls / 'wrong-expectation.json', fixture)
    command = [python, str(ROOT / 'tests/remediation/check_shared.py'),
               '--fixture', str(controls / 'wrong-expectation.json'),
               '--mac-observations', str(out / 'mac-observations.json'), '--out', str(controls / 'failure.json')]
    failure = run(command, ROOT, env, controls / 'failure.log', 30)
    failure_report = json.loads((controls / 'failure.json').read_text())
    # A disappeared known defect must also be reviewed, not silently exempted forever.
    observations = json.loads((out / 'mac-observations.json').read_text())
    exceptions = json.loads((ROOT / 'tests/remediation/known-issues.json').read_text())
    if not exceptions['failures']:
        # Exercise the stale-exception alarm even after every real defect is fixed.
        # This exception exists only inside the disposable control directory.
        case = fixture['cases'][0]
        index = len(case['steps']) - 1
        expected = observations[case['id']][index]['events']
        exceptions['failures'] = [dict(implementation='macos', case=case['id'], step=index,
            field='events', issue='SYNTHETIC-STALE-EXCEPTION', expected=expected, observed=[])]
    known = exceptions['failures'][0]
    write(controls / 'temporary-known-issues.json', exceptions)
    observations[known['case']][known['step']]['events'] = known['expected']
    write(controls / 'fixed-observation.json', observations)
    command = [python, str(ROOT / 'tests/remediation/check_shared.py'),
               '--mac-observations', str(controls / 'fixed-observation.json'),
               '--known-issues', str(controls / 'temporary-known-issues.json'), '--out', str(controls / 'unexpected-pass.json')]
    xpass = run(command, ROOT, env, controls / 'unexpected-pass.log', 30)
    xpass_report = json.loads((controls / 'unexpected-pass.json').read_text())
    result = dict(wrong_assertion_exit=failure['exit_code'],
                  wrong_assertion_detected=failure_report['checks']['UNEXPECTED_FAIL'] > 0,
                  unexpected_pass_exit=xpass['exit_code'],
                  unexpected_pass_detected=xpass_report['checks']['UNEXPECTED_PASS'] > 0)
    result['passed'] = (result['wrong_assertion_exit'] == 1 and result['wrong_assertion_detected']
                        and result['unexpected_pass_exit'] == 1 and result['unexpected_pass_detected'])
    write(controls / 'summary.json', result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True, help='New evidence directory; never overwritten')
    p.add_argument('--repeat', type=int, default=2, choices=[1, 2])
    p.add_argument('--probe-only', action='store_true', help='Development diagnostic; not full acceptance')
    args = p.parse_args()
    if platform.system() != 'Darwin' or sys.version_info < (3, 12):
        p.error('Use macOS and Python 3.12 or newer. Windows is deferred.')
    swift, node = shutil.which('swift'), shutil.which('node')
    if not swift or not node:
        p.error('Install the documented Swift and Node prerequisites first')
    out = args.out.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    report = dict(git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  source_sha256=fingerprint(), system=platform.platform(), architecture=platform.machine(),
                  python=sys.version.split()[0],
                  swift=subprocess.check_output([swift, '--version'], text=True).strip(),
                  node=subprocess.check_output([node, '--version'], text=True).strip(),
                  scope=['macOS', 'workbench'], windows='deferred_by_user',
                  independent_installation_tested=False, full_suite=not args.probe_only,
                  runs=[], gate_passed=False, product_acceptance_passed=False)
    write(out / 'summary.json', report)
    try:
        for number in range(1, args.repeat + 1):
            directory = out / ('run-' + str(number)); directory.mkdir()
            env = isolated_environment(directory, sys.executable, node)
            suites = {}
            # AppKit tests share one main event loop. Running them concurrently
            # can delay timeout callbacks behind unrelated rendering checks.
            command = [swift, 'test', '--no-parallel']
            if args.probe_only:
                command += ['--filter', 'RemediationScenarioProbeTests|CodexAnswerTransportTests']
            suites['swift'] = run(command, ROOT / 'YukioPlayer', env, directory / 'swift.log', 900)
            suites['swift'].update(counts('swift', directory / 'swift.log'))
            if not args.probe_only:
                suites['python'] = run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tools/activity-workbench', '-p', 'test_*.py', '-v'],
                                       ROOT, env, directory / 'python.log', 600)
                suites['python'].update(counts('python', directory / 'python.log'))
                suites['release_python'] = run([sys.executable, '-m', 'unittest', 'discover', '-s', 'scripts', '-p', 'test_*.py', '-v'],
                                       ROOT, env, directory / 'release-python.log', 300)
                suites['release_python'].update(counts('python', directory / 'release-python.log'))
                ui_tests = sorted(str(path.relative_to(ROOT)) for path in (ROOT / 'tools/activity-workbench').glob('test_*.cjs'))
                suites['node'] = run([node, '--test', '--test-reporter=tap', *ui_tests],
                                     ROOT, env, directory / 'node.log', 120)
                suites['node'].update(counts('node', directory / 'node.log'))
            shared = run([sys.executable, str(ROOT / 'tests/remediation/check_shared.py'),
                          '--mac-observations', str(directory / 'mac-observations.json'), '--out', str(directory / 'shared.json')],
                         ROOT, env, directory / 'shared.log', 30)
            shared_report = json.loads((directory / 'shared.json').read_text()) if (directory / 'shared.json').exists() else None
            controls = negative_controls(directory, env, sys.executable) if shared_report else {'passed': False}
            unchanged = fingerprint() == report['source_sha256']
            passed = (all(s['exit_code'] == 0 and s['tests'] is not None and s['tests'] > 0 for s in suites.values())
                      and shared['exit_code'] == 0 and controls['passed'] and unchanged)
            result = dict(run=number, suites=suites, shared_exit=shared['exit_code'],
                          shared_counts=shared_report['checks'] if shared_report else None,
                          negative_controls=controls, source_unchanged=unchanged, gate_passed=passed)
            report['runs'].append(result)
            write(out / 'summary.json', report)
            print(json.dumps(result), flush=True)
            if not passed:
                break
        signatures = [({k:(v['exit_code'],v['tests'],v['skipped']) for k,v in r['suites'].items()},r['shared_counts']) for r in report['runs']]
        report['repeat_consistent'] = len(signatures) == args.repeat and all(s == signatures[0] for s in signatures)
        report['gate_passed'] = report['repeat_consistent'] and all(r['gate_passed'] for r in report['runs'])
        write(out / 'summary.json', report)
        return 0 if report['gate_passed'] else 1
    except Exception as error:
        report['runner_error'] = type(error).__name__ + ': ' + str(error)
        write(out / 'summary.json', report)
        raise


if __name__ == '__main__':
    sys.exit(main())
