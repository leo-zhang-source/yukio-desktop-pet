import io
import json
from pathlib import Path
import sqlite3
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import subprocess

import maintenance_recovery as recovery
from maintenance_lib import sha


class RecoveryTests(unittest.TestCase):
    def test_nas_rejects_ambiguous_target_and_preserves_archive_on_transfer_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root/'source'; source.mkdir()
            (source/'fixture').write_text('synthetic')
            archive = root/'archive'; archive.mkdir()
            summary = recovery.archive_roundtrip(source, archive)
            (archive/'summary.json').write_text(json.dumps(summary))
            before = sha(archive/'evidence.tar.gz')
            out = root/'out'; out.mkdir()
            for host, destination in [('-option', '/volume1/leo/new'), ('nas', '../outside'), ('nas', '/volume1/../new')]:
                with self.assertRaises(ValueError): recovery.nas_roundtrip(archive, out, host, destination)
            with patch.object(recovery.subprocess, 'run', side_effect=subprocess.CalledProcessError(255, 'ssh')):
                with self.assertRaises(subprocess.CalledProcessError):
                    recovery.nas_roundtrip(archive, out, 'nas', '/volume1/leo/new')
            self.assertEqual(sha(archive/'evidence.tar.gz'), before)
            self.assertFalse((out/'restored').exists())

    def test_snapshot_reads_wal_and_never_overwrites_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root/'current.sqlite'
            connection = sqlite3.connect(source)
            try:
                connection.execute('PRAGMA journal_mode=WAL')
                connection.execute('CREATE TABLE records (value TEXT)')
                connection.execute('INSERT INTO records VALUES (?)', ('synthetic',)); connection.commit()
                recovery.snapshot(source, root/'copy.sqlite')
                with sqlite3.connect(root/'copy.sqlite') as restored:
                    self.assertEqual(restored.execute('SELECT * FROM records').fetchall(), [('synthetic',)])
                before = sha(root/'copy.sqlite')
                with self.assertRaises(FileExistsError): recovery.snapshot(source, root/'copy.sqlite')
                self.assertEqual(sha(root/'copy.sqlite'), before)
                with self.assertRaises(TimeoutError): recovery.snapshot(source, root/'timeout.sqlite', timeout=-1)
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM records').fetchone()[0], 1)
            finally: connection.close()

    def test_restored_copy_replays_new_records_without_touching_current(self):
        with tempfile.TemporaryDirectory() as directory:
            result = recovery.drill(Path(directory))
            self.assertTrue(result['passed'], result)
            self.assertEqual(len(result['checks']), 7)

    def test_archive_roundtrip_preserves_executable_and_internal_link(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root/'source'; source.mkdir()
            binary = source/'runner'; binary.write_bytes(b'synthetic'); binary.chmod(0o755)
            (source/'current').symlink_to('runner')
            out = root/'out'; out.mkdir()
            result = recovery.archive_roundtrip(source, out)
            self.assertTrue(result['passed'])
            self.assertTrue(result['manifest']['runner']['executable'])
            self.assertEqual((out/'roundtrip/payload/current').readlink(), Path('runner'))
            with self.assertRaises(FileExistsError): recovery.archive_roundtrip(source, out)
            with self.assertRaises(ValueError): recovery.restore_archive(out/'evidence.tar.gz', '0'*64, root/'bad')
            self.assertFalse((root/'bad').exists())

    def test_archive_rejects_traversal_and_escaping_source_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root/'source'; source.mkdir()
            (source/'secret').symlink_to('../outside')
            out = root/'out'; out.mkdir()
            with self.assertRaises(ValueError): recovery.archive_roundtrip(source, out)
            archive = root/'bad.tar.gz'
            with tarfile.open(archive, 'w:gz') as stream:
                entry = tarfile.TarInfo('../escaped'); entry.size = 1
                stream.addfile(entry, io.BytesIO(b'x'))
            with self.assertRaises(tarfile.FilterError): recovery.restore_archive(archive, sha(archive), root/'restore')
            self.assertFalse((root/'escaped').exists())


if __name__ == '__main__': unittest.main()
