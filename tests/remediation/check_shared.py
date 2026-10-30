#!/usr/bin/env python3
"""Check the same synthetic input against Mac and workbench production parsers.

Exit 0 means no *new* discrepancy. Known product failures remain in the report.
This is not installation acceptance and does not test Windows.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/activity-workbench/core'))
from yukio.parsers_codex import CodexRolloutParser

KEPT = {'activity_end', 'activity_failed', 'task_abort', 'task_failed', 'task_end'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def workbench_observations(fixture):
    result = {}
    for case in fixture['cases']:
        parser = CodexRolloutParser(fixture['session'])
        steps = []
        for index, step in enumerate(case['steps']):
            events = parser.events(step['record'], now=index + 1)
            facts = [r.to_dict() for r in parser.last_tool_results]
            steps.append({'events': [{'kind': e.kind.value, 'id': e.event_id}
                                     for e in events if e.kind.value in KEPT],
                          'result': facts[0] if len(facts) == 1 else None})
        result[case['id']] = steps
    return result


def check(fixture, mac, known):
    ids = [c['id'] for c in fixture['cases']]
    if len(set(ids)) != len(ids) or set(mac) != set(ids):
        raise ValueError('Fixture and Mac case identities must match exactly')
    exceptions = {}
    for item in known['failures']:
        key = (item['implementation'], item['case'], item['step'], item['field'])
        if key in exceptions:
            raise ValueError('Duplicate known-issue key')
        exceptions[key] = item
    used, rows, cases = set(), [], []
    workbench = workbench_observations(fixture)
    for implementation, observations in [('macos', mac), ('workbench', workbench)]:
        for case in fixture['cases']:
            actual_steps = observations[case['id']]
            if len(actual_steps) != len(case['steps']):
                raise ValueError('Observation step count does not match')
            case_rows = []
            for index, (step, actual) in enumerate(zip(case['steps'], actual_steps)):
                checks = [('events', step['expect_events'], actual['events'])]
                if implementation == 'workbench' and 'expect_result' in step:
                    for field, expected in step['expect_result'].items():
                        checks.append(('result.' + field, expected, (actual.get('result') or {}).get(field)))
                for field, expected, observed in checks:
                    key = (implementation, case['id'], index, field)
                    exception = exceptions.get(key)
                    status = 'PASS' if expected == observed else 'UNEXPECTED_FAIL'
                    if exception:
                        used.add(key)
                        if expected == observed:
                            status = 'UNEXPECTED_PASS'
                        elif exception['expected'] == expected and exception['observed'] == observed:
                            status = 'KNOWN_FAIL'
                    row = dict(implementation=implementation, case=case['id'], step=index,
                               field=field, status=status, expected=expected, observed=observed)
                    if exception:
                        row['issue'] = exception['issue']
                    rows.append(row)
                    case_rows.append(row)
            states = {r['status'] for r in case_rows}
            status = ('UNEXPECTED' if states & {'UNEXPECTED_FAIL', 'UNEXPECTED_PASS'} else
                      'KNOWN_FAIL' if 'KNOWN_FAIL' in states else 'PASS')
            cases.append(dict(implementation=implementation, case=case['id'], status=status))
    if set(exceptions) != used:
        raise ValueError('Stale or invalid known-issue references')
    counts = {state: sum(r['status'] == state for r in rows)
              for state in ['PASS', 'KNOWN_FAIL', 'UNEXPECTED_FAIL', 'UNEXPECTED_PASS']}
    return dict(schema_version=1, checks=counts, cases=cases, details=rows,
                gate_passed=not (counts['UNEXPECTED_FAIL'] or counts['UNEXPECTED_PASS']),
                product_acceptance_passed=False,
                independent_installation_tested=False, windows='deferred_by_user',
                limitations=['Mac facts metadata is not exposed by the current parser; only its completion projection is compared.',
                             'activity_end is completion, not a proof of success.',
                             'Synthetic records do not establish compatibility with every real client version.'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fixture', type=Path, default=Path(__file__).parent / 'fixtures/codex-results.json')
    p.add_argument('--known-issues', type=Path, default=Path(__file__).parent / 'known-issues.json')
    p.add_argument('--mac-observations', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    report = check(read(args.fixture), read(args.mac_observations), read(args.known_issues))
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'checks': report['checks'], 'gate_passed': report['gate_passed'],
                      'product_acceptance_passed': False}))
    return 0 if report['gate_passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
