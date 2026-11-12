#!/usr/bin/env python3
"""Synthetic recovery drill and explicit archive round-trip. Never restores in place."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import shlex
import sqlite3
import subprocess
import re
import sys
import tarfile
import time

from maintenance_lib import ROOT, git, sha, source_fingerprint


def snapshot(source, destination, timeout=10):
    """Consistent SQLite snapshot with an exclusive destination and bounded retry."""
    source, destination = Path(source), Path(destination)
    started = time.monotonic()
    def progress(status, remaining, total):
        if time.monotonic() - started > timeout:
            raise TimeoutError('SQLite snapshot timed out; source unchanged, partial output retained')
    with destination.open('xb'):
        pass
    destination.chmod(0o600)
    src = sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True, timeout=1)
    dst = sqlite3.connect(destination)
    try:
        src.backup(dst, pages=64, progress=progress, sleep=0.02)
        if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('snapshot failed integrity check')
    finally:
        src.close()
        dst.close()


def drill(out):
    # Import the shipped storage implementation, not a substitute test database class.
    sys.path.insert(0, str(ROOT/'tools/activity-workbench/core'))
    from yukio.activity_history import ActivityHistory
    source = out/'synthetic-chat.jsonl'
    source.write_text(json.dumps({'type': 'session_meta', 'payload': {'id': 'synthetic-maintenance'}})+'\n')
    database = out/'current.sqlite'
    store = ActivityHistory(database)
    try:
        store.ingest(source)
        before = store.rows()
        checkpoints = store.db.execute('SELECT source_id,state FROM sources ORDER BY source_id').fetchall()
        snapshot(database, out/'snapshot.sqlite')
        with source.open('a') as stream:
            stream.write(json.dumps({'type': 'response_item', 'payload': {'type': 'function_call',
                         'call_id': 'synthetic-call', 'name': 'Read', 'arguments': '{}'}})+'\n')
        store.ingest(source)
        after = store.rows()
    finally:
        store.close()
    current_hash = sha(database)
    shutil.copy2(out/'snapshot.sqlite', out/'restored.sqlite')
    restored = ActivityHistory(out/'restored.sqlite')
    try:
        restored_rows = restored.rows()
        restored_checkpoints = restored.db.execute('SELECT source_id,state FROM sources ORDER BY source_id').fetchall()
        replay = restored.ingest(source)
        continued = restored.rows()
        second = restored.ingest(source)
    finally:
        restored.close()
    # A newer schema must be refused, not silently rebuilt or downgraded.
    snapshot(database, out/'future.sqlite')
    future = sqlite3.connect(out/'future.sqlite')
    future.execute('PRAGMA user_version=999'); future.close()
    future_hash = sha(out/'future.sqlite')
    rejected = False
    try:
        unsupported = ActivityHistory(out/'future.sqlite')
        unsupported.close()
    except ValueError:
        rejected = True
    checks = {
        'snapshot_rows_match': restored_rows == before,
        'snapshot_checkpoints_match': restored_checkpoints == checkpoints,
        'new_record_preserved_in_current': len(after) == len(before)+1 and after[:-1] == before,
        'recovered_copy_continues_exactly': continued == after and replay['events_saved'] == 1,
        'replay_not_duplicated': second['events_saved'] == 0,
        'current_database_untouched_by_restore': sha(database) == current_hash,
        'future_schema_rejected_without_write': rejected and sha(out/'future.sqlite') == future_hash,
    }
    return dict(scope='synthetic_storage_only', checks=checks, passed=all(checks.values()),
                old_records=len(before), current_records=len(after),
                source_revision=git(ROOT, 'rev-parse', 'HEAD'), source_sha256=source_fingerprint(),
                database_hashes={p.name: sha(p) for p in out.glob('*.sqlite')})


def tree_manifest(root):
    # The same mode/symlink validation used by the actual package builder.
    spec = importlib.util.spec_from_file_location('macos_build', ROOT/'scripts/build-macos.py')
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    return builder.manifest(root)


def restore_archive(archive, checksum, destination):
    if sha(archive) != checksum:
        raise ValueError('archive checksum mismatch')
    destination.mkdir(exist_ok=False)
    with tarfile.open(archive, 'r:gz') as stream:
        stream.extractall(destination, filter='data')
    return tree_manifest(destination/'payload')


def archive_roundtrip(source, out):
    source, out = Path(source).resolve(), Path(out).resolve()
    if not source.is_dir() or out.is_relative_to(source):
        raise ValueError('archive output must be outside the selected source directory')
    before = tree_manifest(source)
    archive = out/'evidence.tar.gz'
    with tarfile.open(archive, 'x:gz', dereference=False) as stream:
        stream.add(source, arcname='payload')
    checksum = sha(archive)
    after = restore_archive(archive, checksum, out/'roundtrip')
    checks = dict(source_unchanged=tree_manifest(source) == before, restored_manifest_matches=after == before)
    return dict(scope='explicit_directory_roundtrip', archive=archive.name, sha256=checksum,
                bytes=archive.stat().st_size, files=len(before), manifest=before,
                checks=checks, passed=all(checks.values()))


def nas_roundtrip(source, out, host, remote_directory):
    """Stream one explicitly prepared archive via SSH; SFTP is not required."""
    from pathlib import PurePosixPath
    remote = PurePosixPath(remote_directory)
    if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', host) or not remote.is_absolute()
            or '..' in remote.parts or len(remote.parts) < 3):
        raise ValueError('Use an SSH alias and an explicit new absolute remote directory')
    summary = json.loads((source/'summary.json').read_text())
    archive = source/'evidence.tar.gz'
    if summary.get('passed') is not True or sha(archive) != summary.get('sha256'):
        raise ValueError('A successful, unchanged archive roundtrip is required')
    remote_file = shlex.quote(str(remote/'evidence.tar.gz'))
    started = time.monotonic()
    with (out/'transfer.log').open('w') as log:
        # mkdir (without -p) refuses an old target; noclobber also protects files.
        command = f'umask 077; test -w {shlex.quote(str(remote.parent))} && df -Pk {shlex.quote(str(remote.parent))} && mkdir {shlex.quote(str(remote))}'
        subprocess.run(['ssh', '-oBatchMode=yes', '-oConnectTimeout=10', host, command],
                       stdout=log, stderr=subprocess.STDOUT, timeout=30, check=True)
        with archive.open('rb') as stream:
            subprocess.run(['ssh', '-oBatchMode=yes', host, f'umask 077; set -C; cat > {remote_file}'],
                           stdin=stream, stdout=log, stderr=subprocess.STDOUT, timeout=300, check=True)
        remote_sha = subprocess.check_output(['ssh', '-oBatchMode=yes', host, 'sha256sum '+remote_file],
                                             stderr=log, text=True, timeout=60).split()[0]
        with (out/'readback.tar.gz').open('xb') as stream:
            subprocess.run(['ssh', '-oBatchMode=yes', host, 'cat '+remote_file],
                           stdout=stream, stderr=log, timeout=300, check=True)
    restored = restore_archive(out/'readback.tar.gz', summary['sha256'], out/'restored')
    checks = dict(remote_hash_matches=remote_sha == summary['sha256'],
                  restored_manifest_matches=restored == summary['manifest'],
                  original_unchanged=sha(archive) == summary['sha256'])
    return dict(scope='explicit_archive_NAS_readback', remote=host+':'+str(remote/'evidence.tar.gz'),
                checks=checks, passed=all(checks.values()), sha256=summary['sha256'],
                remote_sha256=remote_sha, readback_sha256=sha(out/'readback.tar.gz'),
                bytes=archive.stat().st_size, files=len(restored), seconds=round(time.monotonic()-started, 2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['drill', 'archive', 'nas'])
    parser.add_argument('--source', type=Path, help='explicit directory for archive; never inferred')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--host', help='configured SSH alias; its configured port is retained')
    parser.add_argument('--remote-directory', help='new directory under an existing writable remote parent')
    args = parser.parse_args()
    if args.action != 'drill' and args.source is None:
        parser.error('archive and nas require an explicit --source')
    if args.action == 'nas' and (not args.host or not args.remote_directory):
        parser.error('nas requires --host and --remote-directory')
    out = args.out.expanduser().resolve()
    if out.is_relative_to(ROOT) or (args.source and out.is_relative_to(args.source.resolve())):
        parser.error('Use a new output directory outside the checkout and archive source')
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    try:
        if args.action == 'drill': result = drill(out)
        elif args.action == 'archive': result = archive_roundtrip(args.source, out)
        else: result = nas_roundtrip(args.source.expanduser().resolve(), out, args.host, args.remote_directory)
        (out/'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
        print(json.dumps({'passed': result['passed'], 'out': str(out), 'scope': result['scope']}))
        return 0 if result['passed'] else 1
    except Exception as error:
        (out/'failure.json').write_text(json.dumps({'error': str(error), 'passed': False})+'\n')
        raise


if __name__ == '__main__':
    raise SystemExit(main())
