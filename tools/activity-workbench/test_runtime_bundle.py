"""The portable runtime must work without importing from the source checkout."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from build_bundle import build


class RuntimeBundleTests(unittest.TestCase):
    def test_packaged_runtime_starts_with_only_its_own_modules(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build(root / 'bundle')
            package = root / 'bundle/Yukio-Activity-Workbench'
            environment = dict(os.environ, PYTHONPATH='', PYTHONNOUSERSITE='1')
            result = subprocess.run(
                [sys.executable, '-I', '-c',
                 'import sys;sys.path.insert(0,sys.argv[1]);from launcher import main;main(["--check","--data-dir",sys.argv[2]])',
                 str(package), str(root / 'new-user-data')],
                cwd=root, env=environment, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIsInstance(json.loads(result.stdout), dict)
            self.assertFalse((root / 'new-user-data').exists())


if __name__ == '__main__':
    unittest.main()
