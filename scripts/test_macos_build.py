"""Guard source/package trust boundaries without invoking a build or installation."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('macbuild', Path(__file__).with_name('build-macos.py'))
builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)


class BuildBoundaryTests(unittest.TestCase):
    def test_downgrade_and_non_numeric_build_are_rejected(self):
        config = json.loads(Path(__file__).with_name('macos-release.json').read_text())
        for build in ('39', '40', '40.0', '41-beta'):
            with self.subTest(build=build), self.assertRaises(ValueError):
                builder.validate(config | {'build': build})

    def test_cached_wrong_dependency_is_rejected_without_network_or_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'dependency.tar.gz'; path.write_bytes(b'corrupted archive')
            with self.assertRaisesRegex(ValueError, 'Cached dependency checksum mismatch'):
                builder.download('https://example.invalid/no-network', '0' * 64, path)
            self.assertEqual(path.read_bytes(), b'corrupted archive')

    def test_bundle_cannot_link_to_files_outside_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); app = root / 'App'; app.mkdir()
            (root / 'private-file').write_text('fixture')
            (app / 'escape').symlink_to('../private-file')
            with self.assertRaisesRegex(ValueError, 'symlink escapes'):
                builder.manifest(app)

    def test_internal_framework_symlinks_and_executable_mode_are_recorded(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); binary = root / 'binary'; binary.write_bytes(b'fixture'); binary.chmod(0o755)
            (root / 'current').symlink_to('binary')
            result = builder.manifest(root)
            self.assertEqual(result['current'], {'symlink': 'binary'})
            self.assertTrue(result['binary']['executable'])


if __name__ == '__main__': unittest.main()
