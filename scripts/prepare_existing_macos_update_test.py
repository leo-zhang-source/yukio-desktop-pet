#!/usr/bin/env python3
"""Build isolated upgrade cases from an actual released old ZIP and a candidate.

Only new .noindex outputs and a new preference domain are used. The installed
App, production signing key, private history and model settings are not inputs.
Serve OUT/feed on loopback, open OUT/installed/Yukio.app, and use Install Update.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import tempfile
import uuid
import xml.etree.ElementTree as ET
from update_channel import load_config, release_base_url


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def executable_code_sha(path):
    # Re-signing changes Mach-O signature bytes. Strip only the signature on a
    # disposable copy to establish that the released executable code was reused.
    with tempfile.TemporaryDirectory(prefix='yukio-code-check-') as temp:
        copy = Path(temp) / 'YukioPlayer'
        shutil.copy2(path, copy)
        subprocess.run(['codesign', '--remove-signature', str(copy)], check=True)
        return sha(copy)


def files(root):
    return {p.relative_to(root).as_posix(): sha(p) for p in root.rglob('*') if p.is_file()}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline-archive', type=Path, required=True)
    p.add_argument('--baseline-sha256', required=True)
    p.add_argument('--target-app', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--sign-tool', type=Path, required=True)
    p.add_argument('--language', choices=['en', 'zh'], default='en')
    p.add_argument('--port', type=int, default=18745)
    p.add_argument('--notes', type=Path, required=True)
    p.add_argument('--notes-zh', type=Path, required=True)
    p.add_argument('--corrupt-download', action='store_true')
    p.add_argument('--identifier', help='Reuse an existing test identity only when replacing its stopped fixture')
    a = p.parse_args()
    if a.out.exists() or a.out.suffix != '.noindex':
        raise SystemExit('Choose a new .noindex output directory')
    if sha(a.baseline_archive) != a.baseline_sha256:
        raise SystemExit('The released baseline ZIP checksum does not match')
    subprocess.run(['codesign', '--verify', '--deep', '--strict', str(a.target_app)], check=True)
    a.out.mkdir(parents=True)
    feed = a.out / 'feed'; feed.mkdir()
    installed = a.out / 'installed'; installed.mkdir()
    subprocess.run(['ditto', '-x', '-k', str(a.baseline_archive), str(installed)], check=True)
    host = installed / 'Yukio.app'
    subprocess.run(['codesign', '--verify', '--deep', '--strict', str(host)], check=True)
    original = plistlib.loads((host/'Contents/Info.plist').read_bytes())
    old_binary = sha(host/'Contents/MacOS/YukioPlayer')
    old_code = executable_code_sha(host/'Contents/MacOS/YukioPlayer')
    target = a.out/'target/Yukio.app'
    subprocess.run(['ditto', str(a.target_app), str(target)], check=True)
    identifier = a.identifier or 'local.yukio.upgrade-test.' + uuid.uuid4().hex[:12]
    if not identifier.startswith('local.yukio.upgrade-test.') or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789.-' for c in identifier):
        raise SystemExit('Only an isolated test identity is allowed')
    sentinel = uuid.uuid4().hex
    profile = a.out.resolve() / 'profile'
    profile.mkdir()
    (profile / '.yukio-upgrade-test-profile').write_text(sentinel)
    (profile / '.yukio-upgrade-test-profile').chmod(0o600)
    # A unique preference domain alone does not isolate collectors or history.
    # These settings belong only to disposable test copies, never the candidate.
    environment = dict(HOME=str(profile), CFFIXED_USER_HOME=str(profile),
        CODEX_HOME=str(profile / '.codex'), CLAUDE_CONFIG_DIR=str(profile / '.claude'),
        DEEPCODE_CONFIG_DIR=str(profile / '.deepcode'), YUKIO_DOCK='1',
        YUKIO_REMINDER_FILE=str(profile / 'reminders.json'), YUKIO_UPGRADE_TEST_TOKEN=sentinel)
    with tempfile.TemporaryDirectory(prefix='yukio-upgrade-test-key-') as temp:
        key = Path(temp)
        launcher = key / 'YukioTestLauncher'
        subprocess.run(['clang', '-target', 'arm64-apple-macos13.0', '-O2', '-Wall', '-Werror',
                        str(Path(__file__).with_name('macos_test_launcher.c')), '-o', str(launcher)], check=True)
        source = key/'generate.swift'
        source.write_text('''import Foundation
import CryptoKit
let dir = URL(fileURLWithPath: CommandLine.arguments[1])
let key = Curve25519.Signing.PrivateKey()
try key.rawRepresentation.base64EncodedData().write(to: dir.appendingPathComponent("private"))
try key.publicKey.rawRepresentation.base64EncodedData().write(to: dir.appendingPathComponent("public"))
''')
        subprocess.run(['swift', str(source), str(key)], check=True)
        (key/'private').chmod(0o600)
        public = (key/'public').read_text()
        for bundle in [host, target]:
            info = plistlib.loads((bundle/'Contents/Info.plist').read_bytes())
            info.update(CFBundleIdentifier=identifier, CFBundleName='Yukio Update Test',
                        CFBundleExecutable='YukioTestLauncher',
                        SUPublicEDKey=public, SUDefaultsDomain=identifier,
                        SUFeedURL=f'http://127.0.0.1:{a.port}/appcast.xml',
                        SURequireSignedFeed=True, SUVerifyUpdateBeforeExtraction=True,
                        SUEnableAutomaticChecks=True, SUAutomaticallyUpdate=False, SUAllowsAutomaticUpdates=False,
                        NSAppTransportSecurity={'NSAllowsLocalNetworking': True},
                        LSEnvironment=environment)
            (bundle/'Contents/Info.plist').write_bytes(plistlib.dumps(info))
            shutil.copy2(launcher, bundle/'Contents/MacOS/YukioTestLauncher')
            subprocess.run(['codesign', '--force', '--sign', '-', str(bundle/'Contents/MacOS/YukioPlayer')], check=True)
            subprocess.run(['codesign', '--force', '--sign', '-', str(bundle)], check=True)
            subprocess.run(['codesign', '--verify', '--deep', '--strict', str(bundle)], check=True)
        target_info = plistlib.loads((target/'Contents/Info.plist').read_bytes())
        archive = feed/'Yukio-update.zip'
        subprocess.run(['ditto', '-c', '-k', '--norsrc', '--keepParent', str(target), str(archive)], check=True)
        sign = [str(a.sign_tool.resolve()), '--ed-key-file', str(key/'private')]
        signature = subprocess.check_output(sign+['-p', str(archive)], text=True).strip()
        ns = 'http://www.andymatuschak.org/xml-namespaces/sparkle'
        ET.register_namespace('sparkle', ns)
        rss = ET.Element('rss', version='2.0'); channel = ET.SubElement(rss, 'channel')
        ET.SubElement(channel, 'title').text = 'Yukio existing-user upgrade test'
        item = ET.SubElement(channel, 'item')
        ET.SubElement(item, 'title').text = 'Yukio ' + target_info['CFBundleShortVersionString']
        ET.SubElement(item, 'link').text = release_base_url(load_config()) + '/releases'
        for language, notes in [('en', a.notes), ('zh', a.notes_zh)]:
            ET.SubElement(item, 'description', {f'{{{ns}}}format': 'markdown',
                '{http://www.w3.org/XML/1998/namespace}lang': language}).text = notes.read_text()
        ET.SubElement(item, 'enclosure', {'url': f'http://127.0.0.1:{a.port}/Yukio-update.zip',
            'length': str(archive.stat().st_size), 'type': 'application/octet-stream',
            f'{{{ns}}}version': target_info['CFBundleVersion'],
            f'{{{ns}}}shortVersionString': target_info['CFBundleShortVersionString'],
            f'{{{ns}}}edSignature': signature})
        ET.ElementTree(rss).write(feed/'appcast.xml', encoding='utf-8', xml_declaration=True)
        subprocess.run(sign+[str(feed/'appcast.xml')], check=True)
        subprocess.run(sign+['--verify', str(archive), signature], check=True)
        if a.corrupt_download:
            raw = bytearray(archive.read_bytes()); raw[len(raw)//2] ^= 1; archive.write_bytes(raw)
    # Only isolated test-domain preferences; never the production domain.
    for name, kind, value in [('language', '-string', a.language), ('UpdateFixtureSentinel', '-string', sentinel), ('scale', '-float', '1.4')]:
        subprocess.run(['defaults', 'write', identifier, name, kind, value], env=os.environ | environment, check=True)
    result = dict(baseline_version=original['CFBundleShortVersionString'], baseline_build=original['CFBundleVersion'],
                  released_baseline_sha256=a.baseline_sha256, original_binary_sha256=old_binary,
                  baseline_executable_code_matches_release=executable_code_sha(host/'Contents/MacOS/YukioPlayer') == old_code,
                  target_version=target_info['CFBundleShortVersionString'], target_build=target_info['CFBundleVersion'],
                  identifier=identifier, preference_sentinel=sentinel, language=a.language,
                  installed_app=str(host.resolve()), target_files=files(target), baseline_files=files(host),
                  temporary_private_key_deleted=True, corrupt_download=a.corrupt_download)
    result.update(environment=environment, profile=str(profile),
                  data_directory=str(profile / 'Library/Application Support/YukioPlayer/activity-observation'),
                  home_isolation='verified-profile launcher restores HOME before exec; verify live process and health identity after launch',
                  test_launcher_sha256=sha(host/'Contents/MacOS/YukioTestLauncher'))
    assert result['baseline_executable_code_matches_release'], 'Baseline executable code changed'
    (a.out/'case.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['target_files','baseline_files','preference_sentinel']}, indent=2))


if __name__ == '__main__':
    main()
