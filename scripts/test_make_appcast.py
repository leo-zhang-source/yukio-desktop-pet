"""Exercise published feed structure with synthetic packages, never a signing key."""
import plistlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

NS='http://www.andymatuschak.org/xml-namespaces/sparkle'


class AppcastTests(unittest.TestCase):
    def test_arm_release_keeps_the_previous_universal_item(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);archive=root/'Yukio.zip';notes=root/'notes.md';tool=root/'sign';fallback=root/'old.xml'
            with zipfile.ZipFile(archive,'w') as z:
                z.writestr('Yukio.app/Contents/Info.plist',plistlib.dumps(dict(CFBundleShortVersionString='0.4.7',CFBundleVersion='28')))
            notes.write_text('Chat navigation and settings.');tool.write_text('#!'+sys.executable+'\nimport sys\nif "-p" in sys.argv:print("SYNTHETIC_SIGNATURE")\n');tool.chmod(0o700)
            fallback.write_text('<rss xmlns:sparkle="'+NS+'"><channel><item><title>Previous universal</title><enclosure url="https://example.com/old.zip" sparkle:version="27" sparkle:edSignature="PREVIOUS" length="1"/></item></channel></rss>')
            output=root/'appcast.xml'
            command=[sys.executable,str(Path(__file__).with_name('make_appcast.py')),'--archive',str(archive),'--notes',str(notes),'--sign-tool',str(tool),'--output',str(output),'--hardware','arm64','--fallback-feed',str(fallback)]
            subprocess.run(command,check=True,capture_output=True)
            items=ET.parse(output).findall('./channel/item');self.assertEqual(len(items),2)
            self.assertEqual(items[0].findtext('{'+NS+'}hardwareRequirements'),'arm64')
            self.assertEqual(items[0].find('enclosure').get('{'+NS+'}version'),'28')
            self.assertIsNotNone(items[0].find('{'+NS+'}informationalUpdate'))
            self.assertEqual(items[0].findtext('link'),'https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.4.7')
            self.assertEqual(items[0].find('enclosure').get('length'),str(archive.stat().st_size))
            self.assertEqual(items[1].find('enclosure').get('{'+NS+'}edSignature'),'PREVIOUS')
            self.assertIsNone(items[1].find('{'+NS+'}hardwareRequirements'))
            bad=subprocess.run(command+['--url','http://example.com/insecure.zip'],capture_output=True)
            self.assertNotEqual(bad.returncode,0)


if __name__=='__main__':unittest.main()
