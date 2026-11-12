#!/usr/bin/env python3
"""Local maintenance: check, audit, verify. Never publishes or changes the App."""
import argparse
from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from zoneinfo import ZoneInfo

from maintenance_lib import ROOT, SUITES, git, inventory_errors, sha, source_fingerprint, verify_evidence


def locked_dependencies(root=ROOT, filename='scripts/macos-build-requirements.txt'):
    path = root / filename
    blocks = path.read_text().replace('\\\n', ' ').splitlines()
    result = {}
    for block in blocks:
        if not block.strip() or block.lstrip().startswith('#'):
            continue
        match = re.fullmatch(r'\s*([\w.-]+)==([\w.+-]+)\s+((?:--hash=sha256:[0-9a-f]{64}\s*)+)\s*', block)
        if not match:
            raise ValueError('all build dependencies must be exactly pinned and SHA256 locked')
        name = match[1].lower().replace('_', '-')
        if name in result:
            raise ValueError('duplicate dependency: ' + name)
        result[name] = {'version': match[2], 'hashes': re.findall(r'sha256:([0-9a-f]{64})', match[3])}
    if not result:
        raise ValueError('empty build dependency lock')
    return result


def due_reviews(policy, today):
    rows = []
    for name, review in policy['reviews'].items():
        checked = date.fromisoformat(review['last_reviewed']) if review.get('last_reviewed') else None
        due = checked + timedelta(days=review['interval_days']) if checked else today
        state = 'due' if due <= today else 'current'
        if checked and checked > today:
            state = 'invalid_future_review'
        rows.append(dict(name=name, owner=review['owner'], last_reviewed=str(checked) if checked else None,
                         next_due=due.isoformat(), state=state, evidence=review.get('evidence')))
    return rows


def check(root=ROOT, today=None):
    today = today or datetime.now(ZoneInfo('America/Los_Angeles')).date()
    policy = json.loads((root / 'maintenance/policy.json').read_text())
    errors = inventory_errors(root)
    if policy['scope'] != {'mac': 'active', 'windows': 'deferred_by_user', 'cloud_cowork': 'deferred_by_user'}:
        errors.append('platform scope requires explicit policy review')
    dependencies = locked_dependencies(root)
    catalogue = json.loads((root / 'maintenance/dependencies.json').read_text())
    if set(dependencies) != set(catalogue['python_build']):
        errors.append('dependency purpose/license catalogue mismatch')
    for name, entry in dependencies.items():
        record = catalogue['python_build'].get(name, {})
        if record.get('version') != entry['version'] or not all(record.get(k) for k in ('purpose', 'license', 'source', 'published')):
            errors.append('dependency review missing or stale: ' + name)
    tools = locked_dependencies(root, 'scripts/maintenance-tools-requirements.txt')
    if tools.get('pip-audit', {}).get('version') != catalogue['maintenance_tools']['pip_audit']:
        errors.append('maintenance auditor and lock disagree')
    resolved = json.loads((root / 'YukioPlayer/Package.resolved').read_text())
    for pin in resolved['pins']:
        if not re.fullmatch('[0-9a-f]{40}', pin['state']['revision']):
            errors.append('Swift dependency revision is not immutable')
        if f'exact: "{pin["state"]["version"]}"' not in (root / 'YukioPlayer/Package.swift').read_text():
            errors.append('Swift manifest and resolved version mismatch')
        if catalogue['swift_runtime'].get(pin['identity'], {}).get('version') != pin['state']['version']:
            errors.append('Swift dependency review is stale')
    config = json.loads((root / 'scripts/macos-release.json').read_text())
    if not re.fullmatch('[0-9a-f]{64}', config['python']['sha256']):
        errors.append('Python runtime archive hash missing')
    if config['python']['version'] not in config['python']['url']:
        errors.append('Python runtime version and archive disagree')
    expected_locks = policy['input_locks']
    for name, checksum in expected_locks.items():
        if sha(root / name) != checksum:
            errors.append('review changed input lock: ' + name)
    workflows = root / '.github/workflows'
    # The archived matrix must not start from PR/push, even if a repository variable changes.
    archived = (workflows / 'agent-portability.yml').read_text()
    if '  pull_request:' in archived or '  push:' in archived or 'if: ${{ false }}' not in archived:
        errors.append('archived portability workflow can run without scope review')
    active = (workflows / 'remediation-checks.yml').read_text()
    if 'windows-' in active or 'schedule:' in active or 'contents: write' in active:
        errors.append('maintenance CI violates local/Mac/read-only scope')
    # A byte-for-byte reviewed lock and workflow are required here. The official
    # CLI separately verifies coverage/provenance; this is not a YAML reimplementation.
    action_policy = json.loads((root / 'maintenance/action-pins.json').read_text())
    for file in action_policy['workflows']:
        for reference in re.findall(r'uses:\s*([^\s#]+)', (root / file).read_text()):
            if reference not in action_policy['references']:
                errors.append('action missing review record: ' + reference)
            elif not re.fullmatch('[0-9a-f]{40}', action_policy['references'][reference]['commit']):
                errors.append('action review has no immutable commit: ' + reference)
    broken_links = []
    for filename in policy['documents']:
        path = root / filename
        if not path.is_file():
            errors.append('missing current document: ' + filename)
            continue
        for link in re.findall(r'\[[^\]]+\]\(([^)]+)\)', path.read_text()):
            if '://' not in link and not link.startswith('#') and not (path.parent / link.split('#')[0]).exists():
                broken_links.append(filename + ': ' + link)
    errors.extend(broken_links)
    reviews = due_reviews(policy, today)
    for review in reviews:
        if review['state'] == 'invalid_future_review':
            errors.append('review date is in the future: ' + review['name'])
        if review['last_reviewed'] and (not review['evidence'] or not (root / review['evidence']).is_file()):
            errors.append('review has no evidence: ' + review['name'])
    compatibility = json.loads((root / 'maintenance/compatibility.json').read_text())
    for row in compatibility['entries']:
        if row['status'] == 'passed' and not all(row.get(k) for k in ('source_revision', 'package_sha256', 'environment', 'evidence')):
            errors.append('compatibility claim has no bound package evidence: ' + row['id'])
    return dict(schema_version=1, checked_on=today.isoformat(), source_revision=git(root, 'rev-parse', 'HEAD'),
                source_sha256=source_fingerprint(root), mechanism_checks_passed=not errors, errors=errors,
                reviews=reviews, open_issues=policy['open_issues'], compatibility=compatibility['entries'],
                product_acceptance=policy['product_acceptance'], remote_enforcement='not_enabled',
                dependencies=dependencies, runtime_python=config['python']['version'], swift_dependencies=resolved['pins'])


def audit_dependencies(auditor, out, root=ROOT):
    dependencies = locked_dependencies(root)
    for name in ('home', 'tmp'):
        (out / name).mkdir()
    env = dict(PATH=os.defpath, HOME=str(out/'home'), TMPDIR=str(out/'tmp'), LANG='en_US.UTF-8',
               PYTHONNOUSERSITE='1', PYTHONIOENCODING='utf-8')
    command = [str(Path(auditor).resolve()), '--disable-pip', '--no-deps', '--require-hashes',
               '-r', str(root/'scripts/macos-build-requirements.txt'), '-f', 'json',
               '--progress-spinner', 'off', '--timeout', '15', '-o', str(out/'audit.json')]
    result = dict(status='unknown', scope='pinned_python_build_dependencies_only',
                  lock_sha256=sha(root/'scripts/macos-build-requirements.txt'),
                  native_and_runtime_review='separate_upstream_review_required', command=command)
    try:
        result['auditor_version'] = subprocess.check_output([command[0], '--version'], env=env, text=True, timeout=10).strip()
        with (out/'audit.log').open('w') as stream:
            run = subprocess.run(command, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=180)
        result['exit_code'] = run.returncode
        if (out/'audit.json').is_file():
            raw = json.loads((out/'audit.json').read_text())
            entries = raw.get('dependencies', [])
            found = {d['name'].lower().replace('_', '-'): d.get('version') for d in entries}
            complete = found == {name: d['version'] for name, d in dependencies.items()} and all('vulns' in d and 'skip_reason' not in d for d in entries)
            vulnerabilities = sum(len(d.get('vulns', [])) for d in entries)
            result.update(complete=complete, vulnerabilities=vulnerabilities, audit_sha256=sha(out/'audit.json'))
            if complete and run.returncode in (0, 1):
                result['status'] = 'findings' if vulnerabilities else ('passed' if run.returncode == 0 else 'unknown')
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        result['error'] = type(error).__name__ + ': ' + str(error)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    status = sub.add_parser('check', help='offline structure, due reviews and truthful pending acceptance')
    status.add_argument('--today', type=date.fromisoformat)
    dep = sub.add_parser('dependencies', help='explicit online read-only audit; never fixes packages')
    dep.add_argument('--auditor', required=True, type=Path)
    verify = sub.add_parser('verify-evidence', help='validate current source, raw logs and optional package')
    verify.add_argument('--evidence', required=True, type=Path)
    verify.add_argument('--revision', help='tested code commit, defaults to current HEAD')
    verify.add_argument('--package', type=Path)
    verify.add_argument('--independent', type=Path)
    for command in (status, dep, verify):
        command.add_argument('--out', required=True, type=Path, help='new directory outside checkout')
    args = parser.parse_args()
    out = args.out.expanduser().resolve()
    if out.is_relative_to(ROOT):
        parser.error('Choose a new evidence directory outside the checkout')
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    try:
        if args.command == 'check':
            result = check(today=args.today)
            success = result['mechanism_checks_passed']
            text = ['# Local maintenance report', '', 'Structure checks: ' + ('passed' if success else 'failed'),
                    'Product acceptance: ' + result['product_acceptance'], 'Remote enforcement: not enabled', '', '## Reviews', '']
            text += [f'- {r["name"]}: {r["state"]}; next due {r["next_due"]}; owner {r["owner"]}' for r in result['reviews']]
            text += ['', '## Open issues', ''] + [f'- {i["id"]}: {i["status"]} — {i["summary"]}' for i in result['open_issues']]
            (out/'report.md').write_text('\n'.join(text)+'\n')
        elif args.command == 'dependencies':
            result = audit_dependencies(args.auditor, out)
            success = result['status'] == 'passed'
        else:
            errors = verify_evidence(args.evidence, args.revision or git(ROOT, 'rev-parse', 'HEAD'),
                                     source_fingerprint(), SUITES, package=args.package, independent=args.independent)
            result = dict(verification_passed=not errors, errors=errors,
                          scope='source_and_package' if args.package else 'source_automatic_checks_only',
                          independent_report_checked=args.independent is not None)
            success = not errors
        (out/'summary.json').write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n')
        print(json.dumps({'out': str(out), 'passed': success, 'status': result.get('status'), 'errors': result.get('errors', [])}))
        return 0 if success else 1
    except Exception as error:
        (out/'failure.json').write_text(json.dumps({'error': str(error), 'passed': False})+'\n')
        raise


if __name__ == '__main__':
    raise SystemExit(main())
