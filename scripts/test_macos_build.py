"""Guard source/package trust boundaries without invoking a build or installation."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from update_channel import load_config, apply_update_settings

spec = importlib.util.spec_from_file_location('macbuild', Path(__file__).with_name('build-macos.py'))
builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)


class BuildBoundaryTests(unittest.TestCase):
    def test_update_channel_rejects_mixed_repositories_and_bad_public_keys(self):
        config = load_config()
        builder.validate(config)
        for changes in [dict(update_feed='https://github.com/leozhang8654/yukio-desktop-pet/releases/latest/download/appcast.xml'),
                        dict(release_repository='../invalid'), dict(update_public_key='broken'),
                        dict(update_public_key='AAAA')]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                builder.validate(config | changes)

    def test_legacy_packager_uses_shared_channel_without_changing_update_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            import plistlib
            import subprocess
            import sys
            path = Path(temporary)/'Info.plist'
            original = dict(CFBundleIdentifier='local.yukio.player', CFBundleVersion='36', SUFeedURL='stale')
            path.write_bytes(plistlib.dumps(original))
            subprocess.run([sys.executable, str(Path(__file__).with_name('update_channel.py')), str(path)], check=True)
            updated = plistlib.loads(path.read_bytes())
            expected = original.copy(); apply_update_settings(expected, load_config())
            self.assertEqual(updated, expected)
            self.assertEqual(updated['SUPublicEDKey'], 'UuIYaOS2mImMarKEoskVy22Juxl1pQeAL5s+mPnqHFg=')
            self.assertEqual(updated['SUFeedURL'], load_config()['update_feed'])

    def test_preview_and_stable_channels_are_separate(self):
        config = load_config()
        preview = 'https://raw.githubusercontent.com/leo-zhang-source/yukio-desktop-pet/main/updates/preview.xml'
        stable = 'https://github.com/leo-zhang-source/yukio-desktop-pet/releases/latest/download/appcast.xml'
        builder.validate(config | dict(release_channel='preview', update_feed=preview))
        builder.validate(config | dict(release_channel='stable', update_feed=stable))
        for changes in [dict(release_channel='stable', update_feed=preview),
                        dict(release_channel='preview', update_feed=stable),
                        dict(release_channel='unknown'), dict(release_tag='../bad')]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                builder.validate(config | changes)

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
