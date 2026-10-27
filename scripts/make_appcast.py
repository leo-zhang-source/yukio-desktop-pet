#!/usr/bin/env python3
"""Build a signed Sparkle feed for a versioned release zip. Key stays in Keychain."""
import argparse
import plistlib
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
import zipfile

SPARKLE = 'http://www.andymatuschak.org/xml-namespaces/sparkle'
ET.register_namespace('sparkle', SPARKLE)
p = argparse.ArgumentParser()
p.add_argument('--archive', type=Path, required=True)
p.add_argument('--notes', type=Path, required=True, help='Short user-facing English update notes')
p.add_argument('--notes-zh', type=Path, required=True, help='Short user-facing Chinese update notes')
p.add_argument('--sign-tool', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--url')
p.add_argument('--hardware', choices=['arm64'])
p.add_argument('--fallback-feed', type=Path, help='Keep older compatible releases for other Macs')
a = p.parse_args()
with zipfile.ZipFile(a.archive) as z:
    info = plistlib.loads(z.read('Yukio.app/Contents/Info.plist'))
version = info['CFBundleShortVersionString']
url = a.url or f'https://github.com/leozhang8654/yukio-desktop-pet/releases/download/v{version}/{a.archive.name}'
if not url.startswith('https://'):
    raise SystemExit('Release archives must use HTTPS')
sign = [str(a.sign_tool.resolve()), '--account', 'yukio-desktop-pet']
signature = subprocess.check_output(sign + ['-p', str(a.archive)], text=True).strip()
rss = ET.Element('rss', version='2.0')
channel = ET.SubElement(rss, 'channel')
ET.SubElement(channel, 'title').text = 'Yukio updates'
item = ET.SubElement(channel, 'item')
ET.SubElement(item, 'title').text = f'Yukio {version}'
ET.SubElement(item, 'link').text = f'https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v{version}'
# An enclosure is an installable update. Do not mark regular releases informational:
# older installed clients would lose their Install Update button.
for language, path in [('en', a.notes), ('zh', a.notes_zh)]:
    ET.SubElement(item, 'description', {f'{{{SPARKLE}}}format': 'markdown',
        '{http://www.w3.org/XML/1998/namespace}lang': language}).text = path.read_text()
ET.SubElement(item, f'{{{SPARKLE}}}minimumSystemVersion').text = '13.0.0'
if a.hardware:
    ET.SubElement(item, f'{{{SPARKLE}}}hardwareRequirements').text = a.hardware
ET.SubElement(item, 'enclosure', {
    'url': url, 'length': str(a.archive.stat().st_size), 'type': 'application/octet-stream',
    f'{{{SPARKLE}}}version': info['CFBundleVersion'],
    f'{{{SPARKLE}}}shortVersionString': version,
    f'{{{SPARKLE}}}edSignature': signature,
})
if a.fallback_feed:
    subprocess.run(sign + ['--verify', str(a.fallback_feed)], check=True)
    for previous in ET.parse(a.fallback_feed).findall('./channel/item'):
        channel.append(previous)
a.output.parent.mkdir(parents=True, exist_ok=True)
ET.indent(rss)
ET.ElementTree(rss).write(a.output, encoding='utf-8', xml_declaration=True)
subprocess.run(sign + [str(a.output)], check=True)
subprocess.run(sign + ['--verify', str(a.archive), signature], check=True)
print(a.output)
