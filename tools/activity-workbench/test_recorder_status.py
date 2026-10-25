from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
import tempfile
import unittest
from collector_status import read_status

class StatusTests(unittest.TestCase):
    def test_allowlist_fresh_stale_stopped_and_malformed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);db=root/'history.sqlite';now=datetime.now(timezone.utc);status=root/'collector-status.json'
            self.assertEqual(read_status(db,'codex',now),{'state':'unavailable'})
            status.write_text(json.dumps(dict(state='waiting',updated_at=now.isoformat(),error_files=0,private='SECRET',path='SECRET')))
            self.assertEqual(read_status(db,'codex',now)['state'],'waiting');self.assertNotIn('SECRET',json.dumps(read_status(db,'codex',now)))
            self.assertEqual(read_status(db,'codex',now+timedelta(seconds=16))['state'],'stale')
            status.write_text(json.dumps(dict(state='stopped',updated_at=now.isoformat())))
            self.assertEqual(read_status(db,'codex',now+timedelta(seconds=90))['state'],'stopped')
            for raw in ['bad','{}','[]','x'*33000]:
                status.write_text(raw);self.assertEqual(read_status(db,'codex',now)['state'],'unavailable')
    def test_latest_valid_status_wins_without_trusting_future_or_wrong_client(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);db=root/'history.sqlite';now=datetime.now(timezone.utc)
            (root/'collector-status.json').write_text(json.dumps(dict(state='waiting',updated_at=now.isoformat())))
            (root/'codex-workbench-status.json').write_text(json.dumps(dict(state='stopped',updated_at=(now-timedelta(seconds=5)).isoformat())))
            self.assertEqual(read_status(db,'codex',now)['state'],'waiting')

            self.assertEqual(read_status(db,'claude',now)['state'],'unavailable')
            (root/'codex-workbench-status.json').write_text(json.dumps(dict(state='failed',updated_at=(now+timedelta(hours=2)).isoformat())))
            self.assertEqual(read_status(db,'codex',now)['state'],'waiting')

    def test_partial_history_is_valid_and_not_mistaken_for_a_dead_recorder(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);now=datetime.now(timezone.utc)
            (root/'codex-workbench-status.json').write_text(json.dumps(dict(state='partial_history',updated_at=now.isoformat(),observation_gaps=1)))
            data=read_status(root/'history.sqlite','codex',now)
            self.assertEqual(data['state'],'partial_history');self.assertEqual(data['observation_gaps'],1)

if __name__=='__main__':unittest.main()
