#!/usr/bin/env python3
"""Read an isolated update result without launching or reactivating its old App.

UI observation of an exited host can reopen it while the installer still owns
replacement. Use this read-only check after Install Update, then inspect the UI
only after target_files_match and target_process_running are both true.
"""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess


def inspect(root):
    case = json.loads((root / 'case.json').read_text())
    host = Path(case['installed_app'])
    actual = {p.relative_to(host).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in host.rglob('*') if p.is_file()}
    info = plistlib.loads((host / 'Contents/Info.plist').read_bytes())
    preferences = {}
    for key, value in [('language', case['language']),
                       ('UpdateFixtureSentinel', case['preference_sentinel']),
                       ('scale', '1.4')]:
        observed = subprocess.check_output(['defaults', 'read', case['identifier'], key], text=True).strip()
        preferences[key] = observed == value
    executable = str(host / 'Contents/MacOS/YukioPlayer')
    processes = []
    for row in subprocess.check_output(['ps', '-axo', 'pid,command'], text=True).splitlines():
        pair = row.strip().split(None, 1)
        if len(pair) == 2 and (pair[1] == executable or pair[1].startswith(executable + ' ')):
            processes.append(int(pair[0]))
    matches = actual == case['target_files']
    signature = subprocess.run(['codesign', '--verify', '--deep', '--strict', str(host)],
                               capture_output=True).returncode == 0
    return dict(baseline_version=case['baseline_version'], target_version=case['target_version'],
                installed_version=info['CFBundleShortVersionString'], installed_build=info['CFBundleVersion'],
                target_files_match=matches, target_file_count=len(case['target_files']),
                baseline_files_unchanged=actual == case['baseline_files'],
                target_process_running=matches and bool(processes), running_pids=processes,
                strict_signature_valid=signature, preferences_preserved=preferences,
                installation_verified=matches and bool(processes) and signature and all(preferences.values()))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('case', type=Path)
    p.add_argument('--out', type=Path)
    a = p.parse_args()
    result = inspect(a.case)
    encoded = json.dumps(result, indent=2) + '\n'
    if a.out:
        a.out.write_text(encoded)
    print(encoded, end='')
