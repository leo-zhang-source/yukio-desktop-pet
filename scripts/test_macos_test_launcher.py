"""Exercise the fixture launcher with a fake product and no GUI or real profile."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


class TestProfileLauncher(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='yukio-profile-launcher-')
        cls.root = Path(cls.temp.name)
        cls.binary = cls.root / 'YukioTestLauncher'
        subprocess.run(['clang', '-target', 'arm64-apple-macos13.0', '-O2', '-Wall', '-Werror',
                        str(Path(__file__).with_name('macos_test_launcher.c')), '-o', str(cls.binary)], check=True)
        product = cls.root / 'YukioPlayer'
        product.write_text('#!/usr/bin/python3\nimport os,sys,json\nprint(json.dumps([os.environ["HOME"],sys.argv[1:]]))\n')
        product.chmod(0o755)
        cls.profile = cls.root / 'private profile'; cls.profile.mkdir()

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def run_fixture(self, token='fixture-token', marker='fixture-token'):
        (self.profile / '.yukio-upgrade-test-profile').write_text(marker)
        env = {'PATH': '/usr/bin:/bin', 'HOME': '/real-home-must-not-be-used',
               'CFFIXED_USER_HOME': str(self.profile)}
        if token is not None: env['YUKIO_UPGRADE_TEST_TOKEN'] = token
        return subprocess.run([str(self.binary), '--check', 'argument with spaces'],
                              env=env, capture_output=True, text=True)

    def test_profile_restored_before_product_and_arguments_preserved(self):
        result = self.run_fixture()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [str(self.profile), ['--check', 'argument with spaces']])

    def test_no_test_token_fails_before_product(self):
        result = self.run_fixture(token=None)
        self.assertEqual(result.returncode, 78); self.assertEqual(result.stdout, '')

    def test_wrong_profile_marker_fails_before_product(self):
        result = self.run_fixture(marker='another-test')
        self.assertEqual(result.returncode, 78); self.assertEqual(result.stdout, '')

    def test_marker_with_valid_prefix_and_extra_bytes_is_rejected(self):
        result = self.run_fixture(token='x' * 127, marker='x' * 128)
        self.assertEqual(result.returncode, 78); self.assertEqual(result.stdout, '')

    def test_marker_with_embedded_null_is_rejected(self):
        result = self.run_fixture(marker='fixture-token\0unrelated')
        self.assertEqual(result.returncode, 78); self.assertEqual(result.stdout, '')


if __name__ == '__main__': unittest.main()
