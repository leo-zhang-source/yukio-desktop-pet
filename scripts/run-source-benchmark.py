#!/usr/bin/env python3
"""Three repetitions per load using synthetic files and real Swift sources.

Diagnostic main-thread call timings, not GUI latency or independent acceptance.
The output directory must be new. Thresholds were fixed before optimization.
"""
import argparse
import json
from pathlib import Path
import platform
import subprocess
import time
from maintenance_lib import git, source_fingerprint

ROOT = Path(__file__).resolve().parents[1]
LIMITS = {'idle': 5, 'normal': 25, 'burst': 100}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    out = args.out.expanduser().resolve()
    if out.is_relative_to(ROOT):
        parser.error("Evidence must be outside the source checkout")
    before = source_fingerprint()
    out.mkdir(parents=True, exist_ok=False)
    binary = out / 'source-benchmark'
    with (out / 'build.log').open('w') as log:
        subprocess.run(['swiftc', '-O', '-o', str(binary),
                        *map(str, sorted((ROOT / 'YukioPlayer/Sources/YukioCore').glob('*.swift'))),
                        str(ROOT / 'tests/remediation/source-benchmark/main.swift'), '-lsqlite3'],
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    runs = []
    report = dict(source_revision=git(ROOT, 'rev-parse', 'HEAD'), source_sha256=before, system=platform.platform(), architecture=platform.machine(),
                  limits_ms=LIMITS, main_thread_call_only=True, gui_latency_tested=False,
                  started_at=time.time(), runs=runs, passed=False)
    for mode, limit in LIMITS.items():
        for repeat in range(1, 4):
            run = json.loads(subprocess.check_output([str(binary), str(out / f'{mode}-{repeat}'), mode]))
            run.update(repeat=repeat, maximum_ms=max(p['total_ms'] for p in run['polls']))
            run['passed'] = run['identity_and_order_passed'] and run['maximum_ms'] <= limit
            runs.append(run)
            print(json.dumps({k:run[k] for k in ('mode','repeat','events','maximum_ms','passed')}), flush=True)
            (out / 'results.json').write_text(json.dumps(report, indent=2)+'\n')
    report['source_unchanged'] = before == source_fingerprint()
    report['passed'] = report['source_unchanged'] and all(r['passed'] for r in runs)
    (out / 'results.json').write_text(json.dumps(report, indent=2)+'\n')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
