import json
from pathlib import Path
import tempfile
import unittest

from server import snapshot


class RuntimeStatusTests(unittest.TestCase):
    def test_gap_count_reaches_local_page_without_private_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); progress = root/'progress.json'; status = root/'status.json'
            progress.write_text('{}')
            status.write_text(json.dumps(dict(state='partial_history', observation_gaps=2,
                              source_path='PRIVATE_SENTINEL', gap_evidence_id='PRIVATE_SENTINEL')))
            result = snapshot(progress, status)
            self.assertEqual(result['collector'], dict(state='partial_history', observation_gaps=2))
            self.assertNotIn('PRIVATE_SENTINEL', json.dumps(result))
