"""Old chat presentation after a reboot, without rewriting saved history."""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from launcher import core_path
sys.path.insert(0, str(core_path()))
from yukio.activity_history import ActivityHistory
from yukio.activity_collector import ActivityCollector
from glance_view import GlanceView
from history_view import HistoryView


class SourceRestartTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.roots = {c: self.root / c for c in ('codex', 'claude')}
        self.databases = {c: self.root / (c + '.sqlite') for c in self.roots}
        self.paths = {}
        # Controlled persistent identities allow this regression on non-Mac CI.
        # Native descriptor/volume behavior has separate tests in history_restart.
        identity = lambda fd, info: 'volume:%s:birth' % info.st_ino
        for target in ('yukio.activity_history.persistent_file_identity',
                       'source_context.persistent_file_identity'):
            mock = patch(target, side_effect=identity)
            mock.start(); self.addCleanup(mock.stop)
        for client, directory in self.roots.items():
            directory.mkdir()
            for suffix in ('A', 'B'):
                session = client + '-' + suffix
                text = 'Please inspect ONLY_' + session
                if client == 'codex':
                    rows = [dict(type='session_meta', payload=dict(id=session)),
                            dict(type='response_item', payload=dict(type='message', role='user',
                                content=[dict(type='input_text', text=text)]))]
                else:
                    rows = [dict(type='user', sessionId=session, uuid=session,
                                 message=dict(role='user', content=text))]
                path = directory / (session + '.jsonl')
                path.write_text(''.join(json.dumps(r) + '\n' for r in rows))
                old = time.time() - 48 * 3600
                os.utime(path, (old, old))
                self.paths[session] = path
                store = ActivityHistory(self.databases[client])
                try: store.ingest(path, source_format=client)
                finally: store.close()
        self.history = HistoryView(self.databases)
        self.glance = GlanceView(self.history, self.roots)

    def change_states(self, change):
        for path in self.databases.values():
            with closing(sqlite3.connect(path)) as db, db:
                for source, raw in db.execute('SELECT source_id,state FROM sources').fetchall():
                    state = json.loads(raw); change(state)
                    db.execute('UPDATE sources SET state=? WHERE source_id=?', (json.dumps(state), source))

    def assert_available(self, expected):
        cards = self.glance.cards()['cards']
        self.assertEqual(len(cards), 4)
        for card in cards:
            self.assertEqual(card['source_unavailable'], not expected)
            detail = self.glance.detail(card['client'], card['key'])
            self.assertEqual(detail['source_unavailable'], not expected)
            if expected:
                self.assertIn('ONLY_' + card['session_id'], detail['goal'])
                for other in self.paths:
                    if other != card['session_id']:self.assertNotIn('ONLY_' + other, detail['goal'])

    def test_old_chats_remain_readable_without_collection_or_database_writes(self):
        self.change_states(lambda s: s.update(file_identity='old-device:' + s['file_identity'].split(':')[1]))
        for client in self.roots:
            store = ActivityHistory(self.databases[client])
            try:
                status = ActivityCollector(store, self.roots[client], source_format=client).poll()
                self.assertEqual(status['discovered_files'], 0)
                self.assertEqual(status['events_saved_this_run'], 0)
            finally: store.close()
        before = {c: p.read_bytes() for c, p in self.databases.items()}
        self.assert_available(True)
        self.assertEqual(before, {c: p.read_bytes() for c, p in self.databases.items()})

    def test_persistent_identity_mismatch_wins_over_unchanged_device_and_inode(self):
        with patch('source_context.persistent_file_identity', return_value='different-volume-or-birth'):
            self.assert_available(False)

    def test_missing_stable_identity_never_falls_back_to_inode_only(self):
        self.change_states(lambda s: s.update(file_identity='old-device:' + s['file_identity'].split(':')[1]))
        with patch('source_context.persistent_file_identity', return_value=None):
            self.assert_available(False)
        self.change_states(lambda s: s.pop('persistent_file_identity', None))
        self.assert_available(False)

    def test_legacy_identity_still_reads_only_when_device_and_inode_match(self):
        self.change_states(lambda s: s.pop('persistent_file_identity', None))
        self.assert_available(True)
        with patch('source_context.persistent_file_identity', return_value=None):
            self.assert_available(True)

    def test_reboot_continuity_does_not_allow_unverified_changed_text(self):
        self.change_states(lambda s: s.update(file_identity='old-device:' + s['file_identity'].split(':')[1]))
        for path in self.paths.values():path.write_text(path.read_text().replace('ONLY_', 'EVIL_'))
        for card in self.glance.cards()['cards']:
            detail = self.glance.detail(card['client'], card['key'])
            self.assertGreater(detail['source_missing'], 0)
            self.assertNotIn('EVIL_', json.dumps(detail))

    def test_same_bytes_replaced_file_and_symlink_cannot_supply_old_text(self):
        for session, path in self.paths.items():
            replacement = self.root / (session + '-replacement')
            replacement.write_bytes(path.read_bytes())
            if session.endswith('A'):
                replacement.replace(path)
            else:
                path.unlink(); path.symlink_to(replacement)
        self.assert_available(False)


if __name__ == '__main__':unittest.main()
