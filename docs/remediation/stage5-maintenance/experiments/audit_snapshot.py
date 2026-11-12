#!/usr/bin/env python3
"""Research-only, read-only checkout audit; writes a new JSON evidence file.

Does not run a release, access accounts, change source, or validate an install.
The synthetic skip experiment evaluates the existing runner's actual predicate.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, text=True).strip()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(root):
    path = root / 'scripts/run-remediation-checks.py'
    source = path.read_text()
    tree = ast.parse(source)
    predicate = next(node.value for node in ast.walk(tree)
                     if isinstance(node, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == 'passed' for t in node.targets))
    scope = dict(suites={'python': {'exit_code': 0, 'tests': 2, 'skipped': 1}},
                 shared={'exit_code': 0}, controls={'passed': True}, unchanged=True)
    # Only the already-inspected boolean predicate is evaluated, with synthetic data.
    accepted_skip = eval(compile(ast.Expression(predicate), str(path), 'eval'), scope)
    commands = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name)
            and t.value.id == 'suites' for t in node.targets):
            commands.append(ast.get_source_segment(source, node))
    commands = '\n'.join(commands)
    web = sorted(p.name for p in (root / 'tools/activity-workbench').glob('test_*.cjs'))
    has_web_discovery = "glob('test_*.cjs')" in source
    web_not_selected = [] if has_web_discovery else [name for name in web if name not in commands]
    workflow = root / '.github/workflows/agent-portability.yml'
    workflow_source = workflow.read_text()
    references = []
    for file in sorted((root / '.github/workflows').glob('*.yml')):
        for line, value in enumerate(file.read_text().splitlines(), 1):
            match = re.search(r'uses:\s*([^\s#]+)', value)
            if match:
                references.append({'file': str(file.relative_to(root)), 'line': line,
                                   'reference': match[1],
                                   'full_sha': bool(re.search(r'@[0-9a-f]{40}$', match[1]))})
    modules = {}
    for name in ('YukioPlayer/Sources/YukioPlayer/main.swift',
                 'YukioPlayer/Sources/YukioCore/ActivityRouter.swift',
                 'tools/activity-workbench/server.py',
                 'tools/activity-workbench/core/yukio/activity_history.py'):
        modules[name] = {'lines': len((root/name).read_text().splitlines()), 'sha256': sha(root/name)}
    return {
        'head': git(root, 'rev-parse', 'HEAD'),
        'branch': git(root, 'branch', '--show-current'),
        'release_configuration': json.loads((root / 'scripts/macos-release.json').read_text()),
        'runner_sha256': sha(path),
        'runner_commands': commands.splitlines(),
        'web_test_files': web,
        'existing_web_files_not_selected': web_not_selected,
        'release_test_files': sorted(p.name for p in (root/'scripts').glob('test_*.py')),
        'runner_selects_release_tests': "'-s', 'scripts'" in commands,
        'synthetic_skip_experiment': {
            'suite': {'exit_code': 0, 'tests': 2, 'skipped': 1},
            'existing_gate_accepts_skipped_test': accepted_skip,
            'predicate': ast.get_source_segment(source, predicate),
            'scope': 'synthetic predicate evaluation; no actual skipped test claimed'},
        'actions_lock_present': (root/'.github/workflows/actions.lock').exists(),
        'action_references': references,
        'portability_workflow_contains_windows_runner': 'windows-latest' in workflow_source,
        'portability_workflow_uses_floating_pyinstaller': 'pyinstaller>=6,<7' in workflow_source,
        'modules': modules,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--published', type=Path, required=True)
    parser.add_argument('--remediation', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    # Exclusive creation prevents silently overwriting an earlier experiment.
    with args.out.open('x') as stream:
        report = {'schema_version': 1, 'scope': 'local_research_only',
                  'published': inspect(args.published.resolve()),
                  'remediation': inspect(args.remediation.resolve())}
        report['web_tests_only_in_remediation'] = sorted(
            set(report['remediation']['web_test_files']) - set(report['published']['web_test_files']))
        json.dump(report, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    print(json.dumps({'out': str(args.out),
                      'release_tests_omitted': not report['published']['runner_selects_release_tests'],
                      'existing_web_files_omitted': report['published']['existing_web_files_not_selected'],
                      'web_tests_only_in_remediation': report['web_tests_only_in_remediation'],
                      'skip_can_pass': report['published']['synthetic_skip_experiment']['existing_gate_accepts_skipped_test']}))


if __name__ == '__main__':
    main()
