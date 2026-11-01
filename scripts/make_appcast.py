#!/usr/bin/env python3
"""Build a signed Sparkle feed for a versioned release zip. Key stays in Keychain."""
import argparse
import plistlib
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from urllib.parse import quote
from update_channel import load_config, release_base_url, validate_release_url

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
config = load_config()
base_url = release_base_url(config)
with zipfile.ZipFile(a.archive) as z:
    info = plistlib.loads(z.read('Yukio.app/Contents/Info.plist'))
for field, expected in [('SUFeedURL', config['update_feed']),
                        ('SUPublicEDKey', config['update_public_key']),
                        ('SURequireSignedFeed', True), ('SUVerifyUpdateBeforeExtraction', True)]:
    if info.get(field) != expected:
        raise SystemExit('Package update configuration does not match release channel: ' + field)
version = info['CFBundleShortVersionString']
tag = quote('v' + version, safe='')
url = a.url or f'{base_url}/releases/download/{tag}/{quote(a.archive.name, safe="")}'
validate_release_url(url)
sign = [str(a.sign_tool.resolve()), '--account', 'yukio-desktop-pet']
# Check fallbacks before signing anything. A valid signature does not make an
# old repository's dead download links usable. Never silently rewrite them:
# each restored asset must first be checked, then the complete feed re-signed.
previous_items = []
if a.fallback_feed:
    previous_items = ET.parse(a.fallback_feed).findall('./channel/item')
    for previous in previous_items:
        for element in previous.iter():
            if 'url' in element.attrib:
                validate_release_url(element.attrib['url'])
            if element.tag in ('link', f'{{{SPARKLE}}}releaseNotesLink') and element.text:
                validate_release_url(element.text.strip())
    subprocess.run(sign + ['--verify', str(a.fallback_feed)], check=True)
signature = subprocess.check_output(sign + ['-p', str(a.archive)], text=True).strip()
rss = ET.Element('rss', version='2.0')
channel = ET.SubElement(rss, 'channel')
ET.SubElement(channel, 'title').text = 'Yukio updates'
item = ET.SubElement(channel, 'item')
ET.SubElement(item, 'title').text = f'Yukio {version}'
ET.SubElement(item, 'link').text = f'{base_url}/releases/tag/{tag}'
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
for previous in previous_items:
    channel.append(previous)
a.output.parent.mkdir(parents=True, exist_ok=True)
ET.indent(rss)
ET.ElementTree(rss).write(a.output, encoding='utf-8', xml_declaration=True)
subprocess.run(sign + [str(a.output)], check=True)
subprocess.run(sign + ['--verify', str(a.output)], check=True)
subprocess.run(sign + ['--verify', str(a.archive), signature], check=True)
print(a.output)
