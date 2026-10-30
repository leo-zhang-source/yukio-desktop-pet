"""Journal continuity across a Mac reboot, including real replacement guards."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from launcher import core_path
sys.path.insert(0, str(core_path()))
from yukio.activity_history import ActivityHistory
from yukio.file_identity import persistent_file_identity


class HistoryRestartTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / 'chat.jsonl'
        self.database = self.root / 'history.sqlite'
        self.source.write_text(json.dumps(dict(type='session_meta', payload=dict(id='chat'))) + '\n')

    def tearDown(self):
        self.temp.cleanup()

    def collect(self, *, identity='volume:file:birth', client='codex'):
        with patch('yukio.activity_history.persistent_file_identity', return_value=identity):
            store = ActivityHistory(self.database)
            try:
                result = store.ingest(self.source, source_format=client)
                return result, store.rows()
            finally:
                store.close()

    def update_state(self, change):
        store = ActivityHistory(self.database)
        try:
            source_id, raw = store.db.execute('SELECT source_id,state FROM sources').fetchone()
            state = json.loads(raw)
            change(state)
            store.db.execute('UPDATE sources SET state=? WHERE source_id=?', (json.dumps(state), source_id))
        finally:
            store.close()

    def change_saved_device(self):
        self.update_state(lambda s: s.update(file_identity='old-device:' + s['file_identity'].split(':')[1]))

    def test_device_number_change_reopens_without_reingesting_in_all_three_readers(self):
        for client in ('codex', 'claude', 'deepcode'):
            with self.subTest(client=client):
                self.database = self.root / (client + '.sqlite')
                _, before = self.collect(client=client)
                self.change_saved_device()
                result, after = self.collect(client=client)
                self.assertEqual(result['events_saved'], 0)
                self.assertEqual(result['generation'], 1)
                self.assertEqual(after, before)
                store = ActivityHistory(self.database)
                try:
                    state = json.loads(store.db.execute('SELECT state FROM sources').fetchone()[0])
                    info = self.source.stat()
                    self.assertEqual(state['file_identity'], '%s:%s' % (info.st_dev, info.st_ino))
                finally:
                    store.close()

    def test_append_after_reboot_keeps_tool_pair_and_sequence(self):
        with self.source.open('a') as stream:
            stream.write(json.dumps(dict(type='response_item', payload=dict(type='function_call', name='Read', call_id='call'))) + '\n')
        _, before = self.collect()
        self.change_saved_device()
        with self.source.open('a') as stream:
            stream.write(json.dumps(dict(type='response_item', payload=dict(type='function_call_output', call_id='call', output={'exit_code': 0}))) + '\n')
        result, after = self.collect()
        self.assertEqual(result['generation'], 1)
        self.assertEqual(result['events_saved'], 1)
        self.assertEqual(after[:-1], before)
        self.assertEqual(after[-1]['kind'], 'tool_result')
        self.assertEqual(after[-1]['result']['outcome'], 'succeeded')
        self.assertEqual(after[-1]['result']['call_id'], 'call')

    def test_identical_bytes_on_a_different_volume_or_reused_inode_still_reset(self):
        for changed in ('other-volume:file:birth', 'volume:new-file:birth', 'volume:file:new-birth'):
            with self.subTest(identity=changed):
                self.database = self.root / (changed.replace(':', '-') + '.sqlite')
                self.collect()
                result, rows = self.collect(identity=changed)
                self.assertEqual(result['generation'], 2)
                self.assertEqual(rows[1]['kind'], 'source_reset')
                self.assertEqual(rows[1]['reason'], 'file_replaced')

    def test_truncation_and_prefix_rewrite_still_reset_with_same_persistent_identity(self):
        for data, reason in [('', 'file_truncated'),
                             (json.dumps(dict(type='session_meta', payload=dict(id='else'))) + '\n', 'prefix_changed')]:
            with self.subTest(reason=reason):
                self.database = self.root / (reason + '.sqlite')
                self.source.write_text(json.dumps(dict(type='session_meta', payload=dict(id='chat'))) + '\n')
                self.collect()
                self.source.write_text(data)
                result, rows = self.collect()
                self.assertEqual(result['generation'], 2)
                self.assertEqual(rows[1]['reason'], reason)

    def test_legacy_checkpoint_is_upgraded_without_replaying_records(self):
        _, before = self.collect(identity=None)
        result, after = self.collect()
        self.assertEqual(result['events_saved'], 0)
        self.assertEqual(after, before)
        self.change_saved_device()
        self.assertEqual(self.collect()[0]['events_saved'], 0)

    def test_legacy_upgrade_after_reboot_requires_inode_and_entire_saved_prefix(self):
        self.collect(identity=None)
        self.update_state(lambda s: s.update(file_identity='12345:' + str(self.source.stat().st_ino)))
        self.assertEqual(self.collect()[0]['events_saved'], 0)
        self.assertEqual(self.collect()[0]['generation'], 1)

        self.database = self.root / 'changed-prefix.sqlite'
        self.collect(identity=None)
        self.update_state(lambda s: s.update(file_identity='12345:' + str(self.source.stat().st_ino)))
        self.source.write_text(self.source.read_text().replace('chat', 'else'))
        result, rows = self.collect()
        self.assertEqual(result['generation'], 2)
        self.assertEqual(rows[1]['reason'], 'prefix_changed')

        self.database = self.root / 'changed-inode.sqlite'
        self.collect(identity=None)
        self.update_state(lambda s: s.update(file_identity='12345:0'))
        self.assertEqual(self.collect()[1][1]['reason'], 'file_replaced')

    def test_unavailable_volume_identity_never_ignores_a_replacement(self):
        self.collect(identity=None)
        self.change_saved_device()
        result, rows = self.collect(identity=None)
        self.assertEqual(result['generation'], 2)
        self.assertEqual(rows[1]['reason'], 'file_replaced')

    def test_partial_record_can_finish_after_reboot_without_replaying_prefix(self):
        self.collect()
        with self.source.open('a') as stream:
            stream.write('{"type":"event_msg","payload":{"type":"task_')
        self.assertEqual(self.collect()[0]['events_saved'], 0)
        self.change_saved_device()
        with self.source.open('a') as stream:
            stream.write('started","turn_id":"turn"}}\n')
        result, rows = self.collect()
        self.assertEqual(result['generation'], 1)
        self.assertEqual(result['events_saved'], 1)
        self.assertEqual([r['kind'] for r in rows], ['session_observed', 'turn_started'])

    @unittest.skipUnless(sys.platform == 'darwin', 'native Mac filesystem API')
    def test_native_mac_identity_tracks_file_replacement_even_with_identical_bytes(self):
        def identity():
            with self.source.open('rb') as stream:
                return persistent_file_identity(stream.fileno(), os.fstat(stream.fileno()))
        before = identity()
        self.assertTrue(before and before.startswith('mac-volume-v1:'))
        self.assertEqual(before, identity())
        replacement = self.root / 'replacement.jsonl'
        replacement.write_bytes(self.source.read_bytes())
        replacement.replace(self.source)
        self.assertNotEqual(before, identity())


if __name__ == '__main__':
    unittest.main()
