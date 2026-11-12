"""Small, offline maintenance contracts shared by the runner and CLI."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SUITES = {
    'swift': ('YukioPlayer/Tests', '*.swift'),
    'python': ('tools/activity-workbench', 'test_*.py'),
    'node': ('tools/activity-workbench', 'test_*.cjs'),
    'release_python': ('scripts', 'test_*.py'),
    'progress_python': ('tools/activity-progress', 'test_*.py'),
}
PREFIXES = ('YukioPlayer/', 'tools/activity-workbench/', 'tools/activity-progress/',
            'YukioWin/core/', 'scripts/', 'tests/', 'config/', 'maintenance/', '.github/', 'assets/')
EXPLICIT = {'YukioWin/scripts/prepare-windows-assets.py', 'docs/mac-guide.html'}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, text=True).strip()


def source_fingerprint(root=ROOT, names=None):
    if names is None:
        names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=root).decode().split('\0')
    digest = hashlib.sha256()
    for name in sorted(set(names)):
        if not name or not (name.startswith(PREFIXES) or name in EXPLICIT):
            continue
        path = root / name
        if path.is_symlink():
            value = 'link:' + str(path.readlink())
        elif path.is_file():
            value = sha(path) + ':' + oct(path.stat().st_mode & 0o777)
        else:
            value = 'missing'
        digest.update((name + '\0' + value + '\0').encode())
    return digest.hexdigest()


def discover(root=ROOT):
    return {name: sorted(str(p.relative_to(root)) for p in (root / folder).rglob(pattern)
                         if '__pycache__' not in p.parts)
            for name, (folder, pattern) in SUITES.items()}


def inventory_errors(root=ROOT):
    expected = json.loads((root / 'maintenance/test-inventory.json').read_text())
    found = discover(root)
    errors = []
    if expected.get('schema_version') != 1 or set(expected.get('suites', {})) != set(SUITES):
        errors.append('test inventory schema/suites mismatch')
    for name, actual in found.items():
        recorded = expected.get('suites', {}).get(name, [])
        if not actual or actual != recorded:
            errors.append(name + ': test files added/removed or inventory empty')
        if name in ('python', 'release_python', 'progress_python') and any(
                Path(p).parent != Path(SUITES[name][0]) for p in actual):
            errors.append(name + ': nested Python tests require an explicit loader review')
    return errors


def parse_counts(kind, text):
    if kind == 'swift':
        matches = re.findall(r'Test run with (\d+) tests? (passed|failed)', text)
        count = int(matches[-1][0]) if matches else None
        success = bool(matches and matches[-1][1] == 'passed')
        skipped = len(re.findall(r'^.*\bTest\b.*\bskipped\b', text, re.M))
        # Some toolchains also emit a numeric summary.
        totals = re.findall(r'(\d+) tests? skipped', text)
        skipped = max(skipped, int(totals[-1]) if totals else 0)
        known = re.findall(r'(\d+) known issues?', text)
        todo = max(map(int, known), default=0)
    elif kind == 'python':
        matches = re.findall(r'^Ran (\d+) tests? in ', text, re.M)
        count = int(matches[-1]) if matches else None
        success = bool(re.search(r'^OK(?:\s*\([^\n]*\))?\s*$', text, re.M))
        skips = re.findall(r'skipped=(\d+)', text)
        skipped = int(skips[-1]) if skips else 0
        todos = re.findall(r'expected failures=(\d+)|expectedFailures=(\d+)', text)
        todo = sum(int(a or b) for a, b in todos)
    elif kind == 'node':
        values = {name: re.findall(r'^# ' + name + r' (\d+)', text, re.M)
                  for name in ('tests', 'fail', 'cancelled', 'skipped', 'todo')}
        count = int(values['tests'][-1]) if values['tests'] else None
        success = all(values[n] and int(values[n][-1]) == 0 for n in ('fail', 'cancelled'))
        skipped = int(values['skipped'][-1]) if values['skipped'] else None
        todo = int(values['todo'][-1]) if values['todo'] else None
    else:
        raise ValueError('unknown test output format')
    return dict(tests=count, skipped=skipped, todo=todo, summary_passed=success)


def suite_passed(suite):
    return (suite.get('exit_code') == 0 and suite.get('timed_out') is False
            and type(suite.get('tests')) is int and suite['tests'] > 0
            and suite.get('skipped') == 0 and suite.get('todo') == 0
            and suite.get('summary_passed') is True)


def run_passed(suites, shared, controls, unchanged, required):
    return (set(suites) == set(required) and all(suite_passed(s) for s in suites.values())
            and shared.get('PASS', 0) > 0
            and all(shared.get(k) == 0 for k in ('KNOWN_FAIL', 'UNEXPECTED_FAIL', 'UNEXPECTED_PASS'))
            and controls.get('passed') is True and unchanged is True)


def safe_evidence(root, name):
    path = root / name
    if Path(name).is_absolute() or not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
        raise ValueError('evidence path escapes its directory')
    return path


def verify_evidence(folder, revision, fingerprint, required, *, package=None, independent=None):
    """Reject stale, partial, altered or merely self-declared successful evidence."""
    folder = Path(folder)
    report = json.loads((folder / 'summary.json').read_text())
    errors = []
    if report.get('schema_version') != 2 or report.get('git_head') != revision:
        errors.append('source revision/schema mismatch')
    if report.get('source_sha256') != fingerprint:
        errors.append('source fingerprint mismatch')
    if report.get('full_suite') is not True or report.get('gate_passed') is not True:
        errors.append('full baseline did not pass')
    if report.get('inventory_errors') != []:
        errors.append('test inventory not verified')
    runs = report.get('runs', [])
    if len(runs) != 2 or report.get('repeat_consistent') is not True:
        errors.append('two consistent runs required')
    hashes = report.get('evidence_hashes', {})
    if not hashes:
        errors.append('missing raw evidence hashes')
    for name, expected in hashes.items():
        path = safe_evidence(folder, name)
        if not path.is_file() or sha(path) != expected:
            errors.append('changed/missing evidence: ' + name)
    signatures = []
    for index, run in enumerate(runs, 1):
        suites = run.get('suites', {})
        if run.get('run') != index or run.get('shared_exit') != 0 or not run_passed(
                suites, run.get('shared_counts') or {}, run.get('negative_controls', {}),
                run.get('source_unchanged'), required):
            errors.append('run failed or incomplete: ' + str(index))
        for name, suite in suites.items():
            log_name = f'run-{index}/' + suite.get('log', '')
            path = safe_evidence(folder, log_name)
            if log_name not in hashes or not path.is_file():
                errors.append('missing suite log: ' + name)
                continue
            kind = 'python' if name.endswith('python') else name
            observed = parse_counts(kind, path.read_text(errors='replace'))
            if any(suite.get(k) != v for k, v in observed.items()):
                errors.append('log/summary mismatch: ' + name)
        for filename, expected in [('shared.json', run.get('shared_counts')),
                                   ('negative-controls/summary.json', run.get('negative_controls'))]:
            name = f'run-{index}/' + filename
            path = safe_evidence(folder, name)
            if name not in hashes or not path.is_file():
                errors.append('missing control evidence: ' + name)
            else:
                value = json.loads(path.read_text())
                if (value.get('checks') if filename == 'shared.json' else value) != expected:
                    errors.append('control summary mismatch: ' + name)
        signatures.append({name: {k: s.get(k) for k in ('tests', 'skipped', 'todo')} for name, s in suites.items()})
    if signatures and any(s != signatures[0] for s in signatures):
        errors.append('repeated counts differ')
    if package is not None:
        package = Path(package)
        build = json.loads((package.parent / 'build.json').read_text())
        entry = build.get('archives', {}).get(package.name, {})
        if (build.get('inputs', {}).get('source_revision') != revision
                or build.get('inputs', {}).get('maintenance_source_sha256') != fingerprint
                or build.get('source_unchanged') is not True
                or entry.get('sha256') != sha(package)):
            errors.append('package/source/hash mismatch')
        if independent is not None:
            acceptance = json.loads(Path(independent).read_text())
            required_fields = ('environment', 'isolation', 'steps', 'evidence')
            if (acceptance.get('status') != 'passed' or acceptance.get('source_revision') != revision
                    or acceptance.get('package_sha256') != sha(package)
                    or not all(acceptance.get(k) for k in required_fields)):
                errors.append('independent acceptance missing/incomplete/mismatched')
    elif independent is not None:
        errors.append('independent acceptance requires an actual package')
    return errors
