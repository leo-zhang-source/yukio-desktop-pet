"""Exercise published feed structure with synthetic packages, never a signing key."""
import plistlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from update_channel import apply_update_settings, load_config

NS='http://www.andymatuschak.org/xml-namespaces/sparkle'


class AppcastTests(unittest.TestCase):
    def test_arm_release_keeps_the_previous_universal_item(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);archive=root/'Yukio.zip';notes=root/'notes.md';notes_zh=root/'notes.zh.md';tool=root/'sign';fallback=root/'old.xml'
            with zipfile.ZipFile(archive,'w') as z:
                info = dict(CFBundleShortVersionString='1.0', CFBundleVersion='28')
                apply_update_settings(info, load_config())
                z.writestr('Yukio.app/Contents/Info.plist', plistlib.dumps(info))
            notes.write_text('## What changed\n\nChoose **Install Update** to continue.');notes_zh.write_text('## 本次更新\n\n点击“安装更新”即可继续。');tool.write_text('#!'+sys.executable+'\nimport sys\nif "-p" in sys.argv:print("SYNTHETIC_SIGNATURE")\n');tool.chmod(0o700)
            fallback.write_text('<rss xmlns:sparkle="'+NS+'"><channel><item><title>Previous universal</title><enclosure url="https://example.com/old.zip" sparkle:version="27" sparkle:edSignature="PREVIOUS" length="1"/></item></channel></rss>')
            output=root/'appcast.xml'
            command=[sys.executable,str(Path(__file__).with_name('make_appcast.py')),'--archive',str(archive),'--notes',str(notes),'--notes-zh',str(notes_zh),'--sign-tool',str(tool),'--output',str(output),'--hardware','arm64','--fallback-feed',str(fallback)]
            subprocess.run(command,check=True,capture_output=True)
            items=ET.parse(output).findall('./channel/item');self.assertEqual(len(items),2)
            self.assertEqual(items[0].findtext('{'+NS+'}hardwareRequirements'),'arm64')
            self.assertEqual(items[0].find('enclosure').get('{'+NS+'}version'),'28')
            self.assertIsNone(items[0].find('{'+NS+'}informationalUpdate'))
            descriptions=items[0].findall('description')
            self.assertEqual(len(descriptions),2)
            self.assertEqual([x.get('{http://www.w3.org/XML/1998/namespace}lang') for x in descriptions],['en','zh'])
            self.assertTrue(all(x.get('{'+NS+'}format')=='markdown' and '<pre>' not in x.text for x in descriptions))
            self.assertIn('安装更新',descriptions[1].text)
            self.assertEqual(items[0].findtext('link'),'https://github.com/leo-zhang-source/yukio-desktop-pet/releases/tag/v1.0')
            self.assertEqual(items[0].find('enclosure').get('url'),'https://github.com/leo-zhang-source/yukio-desktop-pet/releases/download/v1.0/Yukio.zip')
            self.assertEqual(items[0].find('enclosure').get('length'),str(archive.stat().st_size))
            self.assertEqual(items[1].find('enclosure').get('{'+NS+'}edSignature'),'PREVIOUS')
            self.assertIsNone(items[1].find('{'+NS+'}hardwareRequirements'))
            subprocess.run(command + ['--tag', 'v1.0-preview.1'], check=True, capture_output=True)
            preview = ET.parse(output).find('./channel/item')
            self.assertTrue(preview.findtext('link').endswith('/v1.0-preview.1'))
            self.assertIn('/v1.0-preview.1/', preview.find('enclosure').get('url'))
            invalid = subprocess.run(command + ['--tag', '../invalid'], capture_output=True)
            self.assertNotEqual(invalid.returncode, 0)
            bad=subprocess.run(command+['--url','http://example.com/insecure.zip'],capture_output=True)
            self.assertNotEqual(bad.returncode,0)

    def test_migration_rejects_stale_packages_and_retired_fallback_links_before_signing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive, notes, output, tool, fallback = [root/name for name in ('Yukio.zip','notes.md','appcast.xml','sign','old.xml')]
            marker = root/'sign-called'
            tool.write_text('#!' + sys.executable + '\nfrom pathlib import Path\nPath(' + repr(str(marker)) + ').touch()\n')
            tool.chmod(0o700); notes.write_text('Fixture update')
            info = dict(CFBundleShortVersionString='5.4', CFBundleVersion='47')
            apply_update_settings(info, load_config())
            command = [sys.executable, str(Path(__file__).with_name('make_appcast.py')), '--archive', str(archive),
                       '--notes', str(notes), '--notes-zh', str(notes), '--sign-tool', str(tool), '--output', str(output)]
            retired = 'https://github.com/leozhang8654/yukio-desktop-pet/releases/download/v5.3/Yukio.zip'
            for field, value in [('SUFeedURL', retired), ('SUPublicEDKey', 'different-key'),
                                  ('SURequireSignedFeed', False), ('SUVerifyUpdateBeforeExtraction', False)]:
                with self.subTest(field=field):
                    with zipfile.ZipFile(archive, 'w') as z:
                        z.writestr('Yukio.app/Contents/Info.plist', plistlib.dumps(info | {field: value}))
                    result = subprocess.run(command, capture_output=True, text=True)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(field, result.stderr)
                    self.assertFalse(marker.exists()); self.assertFalse(output.exists())
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('Yukio.app/Contents/Info.plist', plistlib.dumps(info))
            for content in [f'<enclosure url="{retired}"/>', f'<link>{retired}</link>',
                            f'<sparkle:releaseNotesLink>{retired}</sparkle:releaseNotesLink>']:
                with self.subTest(content=content):
                    fallback.write_text(f'<rss xmlns:sparkle="{NS}"><channel><item>{content}</item></channel></rss>')
                    result = subprocess.run(command + ['--fallback-feed', str(fallback)], capture_output=True, text=True)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('Retired release URL', result.stderr)
                    self.assertFalse(marker.exists()); self.assertFalse(output.exists())
            result = subprocess.run(command + ['--url', retired], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Retired release URL', result.stderr)
            self.assertFalse(marker.exists())


if __name__=='__main__':unittest.main()
