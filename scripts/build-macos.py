#!/usr/bin/env python3
"""Build the complete Mac candidate from one immutable Git commit.

Requires an Apple Silicon Mac, Command Line Tools and Python 3.12+ to bootstrap.
Downloads are pinned; the packaged Python and build environment are recreated.
No installed App, user data, signing key, or developer binary is an input.
This command does not install, publish, or claim independent-user acceptance.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
from update_channel import validate_update_channel, apply_update_settings
from maintenance_lib import source_fingerprint

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_NAMES = {'local-explanation-options.json', 'auth.json', 'credentials.json', 'lan-model.json', 'work-context.json',
                 'page-explanation-policy.json', 'explanation-provider.json', '.env'}
MACHO = {bytes.fromhex(value) for value in
         ('feedface', 'cefaedfe', 'feedfacf', 'cffaedfe', 'cafebabe', 'bebafeca', 'cafebabf', 'bfbafeca')}


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''): h.update(chunk)
    return h.hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode().strip()


def version(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d+(?:\.\d+){0,2}', value):
        raise ValueError('Expected a numeric version')
    parts = tuple(map(int, value.split('.')))
    return parts + (0,) * (3 - len(parts))


def validate(config):
    version(config['version']); version(config['workbench_version'])
    validate_update_channel(config)
    tag = config.get('release_tag')
    if tag and not re.fullmatch(r'v[0-9][A-Za-z0-9.-]*', tag):
        raise ValueError('Invalid release tag')
    if version(config['build']) <= version(config['upgrade_baseline_build']):
        raise ValueError('Build must be newer than the selected upgrade baseline')
    if config['architecture'] != 'arm64' or config['minimum_macos'] != '13.0':
        raise ValueError('This candidate pipeline is qualified for Mac arm64 / macOS 13+')
    if not config['python']['url'].startswith('https://github.com/astral-sh/python-build-standalone/releases/download/'):
        raise ValueError('Python must have an explicit official release source')
    if not re.fullmatch(r'[0-9a-f]{64}', config['python']['sha256']):
        raise ValueError('Python archive checksum required')


def manifest(root):
    result = {}
    for p in sorted(root.rglob('*')):
        name = p.relative_to(root).as_posix()
        if p.is_symlink():
            if not p.resolve().is_relative_to(root.resolve()):
                raise ValueError('Package symlink escapes bundle: ' + name)
            result[name] = {'symlink': os.readlink(p)}
        elif p.is_file():
            result[name] = {'sha256': sha(p), 'executable': bool(p.stat().st_mode & 0o111)}
    return result


def download(url, checksum, destination):
    if not destination.exists():
        partial = destination.with_suffix('.part')
        with urllib.request.urlopen(url, timeout=60) as response, partial.open('xb') as stream:
            shutil.copyfileobj(response, stream, length=1048576)
        if sha(partial) != checksum:
            raise ValueError('Downloaded dependency checksum mismatch; partial retained')
        partial.rename(destination)
    if sha(destination) != checksum:
        raise ValueError('Cached dependency checksum mismatch; no build attempted')


def native_dependencies(app):
    """Reject author-machine library paths or a falsely low minimum OS."""
    results = {}
    for path in sorted(app.rglob('*')):
        if path.is_symlink() or not path.is_file(): continue
        with path.open('rb') as stream: magic = stream.read(4)
        if magic not in MACHO: continue
        linked = subprocess.check_output(['otool', '-L', str(path)], text=True)
        deps = [line.strip().split(' (', 1)[0] for line in linked.splitlines()[1:] if 'compatibility version' in line]
        for dep in deps:
            if not dep.startswith(('@rpath/', '@loader_path/', '@executable_path/', '/usr/lib/', '/System/Library/')):
                raise ValueError('Nonportable linked library: ' + dep)
        commands = subprocess.check_output(['otool', '-l', str(path)], text=True)
        minimums = re.findall(r'\bminos\s+(\d+(?:\.\d+)*)', commands)
        minimums += re.findall(r'cmd LC_VERSION_MIN_MACOSX\s+cmdsize \d+\s+version (\d+(?:\.\d+)*)', commands)
        if not minimums or any(version(v) > version('13.0') for v in minimums):
            raise ValueError('Unsupported minimum OS in ' + path.name + ': ' + str(minimums))
        results[path.relative_to(app).as_posix()] = {'libraries': deps, 'minimum_macos': minimums}
    if not results: raise ValueError('No native code found')
    return results


def build(args):
    if sys.version_info < (3, 12) or sys.platform != 'darwin' or platform.machine() != 'arm64':
        raise ValueError('Use Python 3.12+ on an Apple Silicon Mac')
    commit = git('rev-parse', '--verify', args.revision + '^{commit}')
    own = subprocess.check_output(['git', 'show', commit + ':scripts/build-macos.py'], cwd=ROOT)
    if hashlib.sha256(own).hexdigest() != sha(Path(__file__)):
        raise ValueError('Run the build entry from the requested commit; commit reviewed changes first')
    out, cache = args.out.expanduser().resolve(), args.cache.expanduser().resolve()
    if out.exists() or out.is_relative_to(ROOT):
        raise ValueError('Choose a new output folder outside the source checkout')
    if shutil.disk_usage(out.parent).free < 3 * 1024**3:
        raise ValueError('At least 3 GiB free is required before starting; use a larger build volume')
    out.mkdir(mode=0o700); args.created_output = True
    cache.mkdir(parents=True, exist_ok=True)
    for name in ('logs', 'work', 'home', 'tmp'): (out / name).mkdir()
    env = {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'HOME': str(out / 'home'),
           'CFFIXED_USER_HOME': str(out / 'home'), 'TMPDIR': str(out / 'tmp') + '/',
           'LANG': 'en_US.UTF-8', 'LC_ALL': 'en_US.UTF-8', 'PYTHONNOUSERSITE': '1',
           'PYTHONDONTWRITEBYTECODE': '1', 'PIP_DISABLE_PIP_VERSION_CHECK': '1',
           'MACOSX_DEPLOYMENT_TARGET': '13.0', 'COPYFILE_DISABLE': '1'}
    def run(label, command, cwd=None, extra=None):
        print(label, flush=True)
        with (out / 'logs' / (label + '.log')).open('w') as log:
            subprocess.run([str(x) for x in command], cwd=cwd or out, env=env | (extra or {}),
                           stdout=log, stderr=subprocess.STDOUT, check=True)
    snapshot = out / 'work/source'; snapshot.mkdir()
    source_tar = out / 'work/source.tar'
    with source_tar.open('wb') as stream:
        subprocess.run(['git', 'archive', '--format=tar', commit], cwd=ROOT, stdout=stream, check=True)
    with tarfile.open(source_tar) as archive: archive.extractall(snapshot, filter='data')
    source_tar.unlink()  # Generated duplicate, not source or user data.
    source_before = manifest(snapshot)
    config = json.loads((snapshot / 'scripts/macos-release.json').read_text()); validate(config)
    caller_changes = git('status', '--porcelain').splitlines()
    write(out / 'source-files.json', source_before)
    write(out / 'build-start.json', {'commit': commit, 'source_tree': git('rev-parse', commit + '^{tree}'),
                                  'caller_changes_excluded': caller_changes, 'snapshot_clean': True})
    python_archive = cache / (config['python']['sha256'] + '.tar.gz')
    download(config['python']['url'], config['python']['sha256'], python_archive)
    with tarfile.open(python_archive) as archive: archive.extractall(out / 'work', filter='data')
    python = out / 'work/python/bin/python3'
    actual = subprocess.check_output([str(python), '-c', 'import platform; print(platform.python_version())'], env=env, text=True).strip()
    if actual != config['python']['version']: raise ValueError('Pinned Python version mismatch')
    run('create-build-environment', [python, '-m', 'venv', out / 'work/venv'])
    python = out / 'work/venv/bin/python'
    run('install-locked-dependencies', [python, '-m', 'pip', 'install', '--require-hashes', '--only-binary=:all:',
        '--no-cache-dir', '--report', out / 'dependency-install.json', '-r', snapshot / 'scripts/macos-build-requirements.txt'])
    run('build-player', ['swift', 'build', '-c', 'release', '--force-resolved-versions',
        '--package-path', snapshot / 'YukioPlayer', '--scratch-path', out / 'work/swift'])
    run('prepare-lossless-pages', [python, snapshot / 'YukioWin/scripts/prepare-windows-assets.py',
        '--source', snapshot / 'YukioPlayer/Resources/Assets', '--output', out / 'work/pages/Assets'])
    run('build-workbench', [python, snapshot / 'tools/activity-workbench/build_macos.py', '--out', out / 'work/workbench',
        '--version', config['workbench_version'], '--build-number', config['build']])
    app = out / 'Yukio.app'; contents = app / 'Contents'; resources = contents / 'Resources'
    (contents / 'MacOS').mkdir(parents=True); resources.mkdir(); (contents / 'Frameworks').mkdir()
    binary = out / 'work/swift/arm64-apple-macosx/release/YukioPlayer'
    shutil.copy2(binary, contents / 'MacOS/YukioPlayer')
    for name in ('Assets', 'BACKGROUND-ANSWERS.md', 'AppIcon.icns'):
        p = snapshot / 'YukioPlayer/Resources' / name
        if p.is_dir(): shutil.copytree(p, resources / name)
        else: shutil.copy2(p, resources / name)
    shutil.copy2(snapshot / 'docs/mac-guide.html', resources / 'UserGuide.html')
    source_assets = manifest(snapshot / 'YukioPlayer/Resources/Assets')
    pages = out / 'work/pages/Assets'
    for p in pages.rglob('windows-pages'):
        if p.is_dir(): shutil.copytree(p, resources / 'Assets' / p.relative_to(pages))
    target = resources / 'deepseek-answers'; target.mkdir()
    for p in (snapshot / 'YukioPlayer/integrations/deepseek').iterdir():
        if p.suffix == '.mjs' or p.name == 'package.json': shutil.copy2(p, target / p.name)
    runtime = resources / 'activity-workbench'; runtime.mkdir()
    component = out / 'work/workbench/雪绪活动工作台.app/Contents/Resources'
    for name in ('runtime', 'workbench'): shutil.copytree(component / name, runtime / name, symlinks=True)
    shutil.copy2(component / 'THIRD-PARTY-NOTICES.txt', runtime / 'THIRD-PARTY-NOTICES.txt')
    # This repository currently has no root license file; do not invent terms.
    for name in ('LICENSE', 'LICENSE.md', 'LICENSE.txt'):
        if (snapshot / name).is_file(): shutil.copy2(snapshot / name, resources / name)
    python_license = out / 'work/python/lib/python3.12/LICENSE.txt'
    shutil.copy2(python_license, runtime / 'PYTHON-LICENSE.txt')
    for language, name in [('en', 'Yukio'), ('zh-Hans', '雪绪')]:
        folder = resources / (language + '.lproj'); folder.mkdir()
        (folder / 'InfoPlist.strings').write_text('"CFBundleDisplayName" = "' + name + '";\n"CFBundleName" = "' + name + '";\n')
    sparkle = out / 'work/swift/artifacts/sparkle/Sparkle/Sparkle.xcframework/macos-arm64_x86_64/Sparkle.framework'
    run('embed-sparkle', ['ditto', sparkle, contents / 'Frameworks/Sparkle.framework'])
    run('link-frameworks', ['install_name_tool', '-add_rpath', '@executable_path/../Frameworks', contents / 'MacOS/YukioPlayer'])
    info = dict(CFBundleIdentifier=config['bundle_identifier'], CFBundleName='雪绪', CFBundleDisplayName='雪绪',
        CFBundleExecutable='YukioPlayer', CFBundleIconFile='AppIcon', CFBundlePackageType='APPL',
        CFBundleShortVersionString=config['version'], CFBundleVersion=config['build'],
        CFBundleLocalizations=['zh-Hans', 'en'], LSMinimumSystemVersion=config['minimum_macos'],
        LSUIElement=True, NSHighResolutionCapable=True, NSAppTransportSecurity={'NSAllowsLocalNetworking': True},
        SUFeedURL=config['update_feed'], SUPublicEDKey=config['update_public_key'], SURequireSignedFeed=True,
        SUVerifyUpdateBeforeExtraction=True, SUEnableAutomaticChecks=True, SUScheduledCheckInterval=21600,
        SUAutomaticallyUpdate=False, SUAllowsAutomaticUpdates=False, SUEnableInstallerLauncherService=False,
        YukioSourceRevision=commit, YukioWorkbenchVersion=config['workbench_version'], YukioBuildChannel='candidate')
    apply_update_settings(info, config)
    info['YukioBuildChannel'] = config.get('release_channel', 'candidate')
    if config.get('release_tag'): info['YukioReleaseTag'] = config['release_tag']
    (contents / 'Info.plist').write_bytes(plistlib.dumps(info))
    inputs = {'source_revision': commit, 'source_tree': git('rev-parse', commit + '^{tree}'), 'configuration': config,
              'maintenance_source_sha256': source_fingerprint(snapshot, source_before),
              'dependency_lock_sha256': sha(snapshot / 'scripts/macos-build-requirements.txt'),
              'swift_package_lock_sha256': sha(snapshot / 'YukioPlayer/Package.resolved'), 'original_assets': source_assets}
    write(resources / 'BUILD-PROVENANCE.json', inputs)
    for path in app.rglob('*'):
        if path.name in PRIVATE_NAMES or path.suffix.lower() in ('.sqlite', '.sqlite3', '.db', '.jsonl'):
            raise ValueError('Unexpected private-data-shaped file in App: ' + path.name)
    packaged_assets = manifest(resources / 'Assets')
    for name, expected in source_assets.items():
        if expected != packaged_assets.get(name): raise ValueError('Original asset changed: ' + name)
    write(out / 'native-dependencies.json', native_dependencies(app))
    run('sign-candidate', ['codesign', '--force', '--sign', '-', app])
    run('verify-signature', ['codesign', '--verify', '--deep', '--strict', app])
    run('check-packaged-assets', [contents / 'MacOS/YukioPlayer', '--check'])
    label = config['release_tag'][1:] if config.get('release_tag') else config['version'] + '-candidate-' + config['build']
    archive = out / ('Yukio-' + label + '-macOS-arm64.zip')
    distribution = out / 'work/distribution'; distribution.mkdir()
    shutil.copytree(app, distribution / 'Yukio.app', symlinks=True)
    shutil.copy2(resources / 'UserGuide.html', distribution / 'Start Here.html')
    run('archive-app', ['ditto', '-c', '-k', '--norsrc', distribution, archive])
    dmg = archive.with_suffix('.dmg')
    run('create-installer', ['sh', snapshot / 'YukioPlayer/scripts/package-macos-dmg.sh', app, dmg],
        extra={'YUKIO_DMG_PYTHON': str(python)})
    # Dependency resolution may create workspace state, but must not edit tracked inputs.
    for name, before in source_before.items():
        p = snapshot / name
        after = {'symlink': os.readlink(p)} if p.is_symlink() else {'sha256': sha(p), 'executable': bool(p.stat().st_mode & 0o111)}
        if before != after: raise ValueError('Source input changed during build: ' + name)
    result = {'inputs': inputs, 'caller_changes_excluded': caller_changes, 'source_unchanged': True,
              'tools': {'swift': subprocess.check_output(['swift', '--version'], text=True).strip(), 'macos': platform.mac_ver()[0]},
              'files': manifest(app), 'archives': {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in (archive, dmg)},
              'signing': 'ad_hoc_not_notarized', 'public_release_ready': False, 'independent_installation_verified': False,
              'windows': 'deferred_by_user', 'production_app_or_profile_used': False}
    write(out / 'build.json', result)
    (out / 'SHA256SUMS.txt').write_text(''.join(v['sha256'] + '  ' + k + '\n' for k, v in result['archives'].items()))
    print(json.dumps({'out': str(out), 'source_revision': commit, 'archives': result['archives'], 'public_release_ready': False}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', required=True, help='Reviewed commit; uncommitted changes are excluded')
    parser.add_argument('--out', type=Path, required=True, help='New folder outside the repository')
    parser.add_argument('--cache', type=Path, required=True, help='Checksum-verified public download cache')
    args = parser.parse_args()
    try: build(args)
    except Exception as error:
        if getattr(args, 'created_output', False): write(args.out / 'failure.json', {'type': type(error).__name__, 'error': str(error), 'public_release_ready': False})
        raise
