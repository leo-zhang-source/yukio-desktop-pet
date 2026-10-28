#!/usr/bin/env python3
"""Package a tested player binary with the existing verified workbench runtime.

Use an explicit player baseline so local settings, skins and updater resources
are not accidentally replaced by an older development checkout. No user profile
or model configuration is bundled. This creates a new output; never an install.
"""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import re
import shutil
import subprocess


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(root):
    return {p.relative_to(root).as_posix(): digest(p) for p in sorted(root.rglob('*')) if p.is_file()}


def build(base_app, workbench_app, binary, source, output, version=None, build_number=None, revision=None):
    if output.exists():
        raise ValueError('Choose a new output directory')
    baseline_info = plistlib.loads((base_app / 'Contents/Info.plist').read_bytes())
    if version:
        if not re.fullmatch(r'\d+\.\d+(?:\.\d+)?', version) or not build_number or not re.fullmatch(r'\d+(?:\.\d+){0,2}', build_number) or not revision or not re.fullmatch(r'[0-9a-f]{40}', revision):
            raise ValueError('A public release needs a version, numeric build and exact source revision')
        if tuple(map(int, build_number.split('.'))) <= tuple(map(int, baseline_info['CFBundleVersion'].split('.'))):
            raise ValueError('The release must be newer than its baseline')
    subprocess.run(['codesign', '--verify', '--deep', '--strict', str(base_app)], check=True)
    subprocess.run(['codesign', '--verify', '--deep', '--strict', str(workbench_app)], check=True)
    sources = {p.relative_to(source).as_posix(): digest(p) for folder in ('Sources', 'Tests')
               for p in sorted((source / folder).rglob('*.swift'))}
    before = {name: value for name, value in files(base_app / 'Contents/Resources').items()
              if not name.startswith('activity-workbench/')}
    workbench = files(workbench_app / 'Contents/Resources')
    output.mkdir(parents=True)
    app = output / 'Yukio.app'
    shutil.copytree(base_app, app, symlinks=True)
    executable = app / 'Contents/MacOS/YukioPlayer'
    shutil.copy2(binary, executable)
    linked = subprocess.check_output(['otool', '-l', str(executable)], text=True)
    if '@executable_path/../Frameworks' not in linked:
        subprocess.run(['install_name_tool', '-add_rpath', '@executable_path/../Frameworks', str(executable)], check=True)
    resources = app / 'Contents/Resources'
    target = resources / 'activity-workbench'
    if target.exists():
        shutil.rmtree(target)  # Only the newly copied candidate, never the installed app.
    target.mkdir()
    for name in ('runtime', 'workbench'):
        shutil.copytree(workbench_app / 'Contents/Resources' / name, target / name, symlinks=True)
    shutil.copy2(workbench_app / 'Contents/Resources/THIRD-PARTY-NOTICES.txt', target / 'THIRD-PARTY-NOTICES.txt')
    # Inputs are installed application resources only, not Application Support.
    for p in target.rglob('*'):
        if p.name in ('lan-model.json', 'work-context.json', 'page-explanation-policy.json', 'explanation-provider.json') or p.suffix in ('.sqlite', '.sqlite3'):
            raise ValueError('Private profile data must not enter the package')
    plist = app / 'Contents/Info.plist'
    info = plistlib.loads(plist.read_bytes())
    info['CFBundleLocalizations'] = ['zh-Hans', 'en']
    workbench_info = plistlib.loads((workbench_app / 'Contents/Info.plist').read_bytes())
    workbench_version = workbench_info['CFBundleShortVersionString']
    info.update(CFBundleVersion=build_number or '27.3', YukioLocalFeature='chat-navigation-and-settings-layout',
                YukioWorkbenchVersion=workbench_version, YukioIntegrationSourceSHA256=hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest())
    if version:
        info.update(CFBundleShortVersionString=version, YukioSourceRevision=revision,
                    YukioFeature='activity-workbench-language-and-context')
        for key in ('YukioLocalFeature', 'YukioLocalRepair'):
            info.pop(key, None)
    # Yukio is not sandboxed. Sparkle forbids opting into the sandbox-only
    # installer launcher for this host; do not inherit a legacy true value.
    info['SUEnableInstallerLauncherService'] = False
    # Permit only local networking; external HTTPS trust checks are unchanged.
    info.setdefault('NSAppTransportSecurity', {})['NSAllowsLocalNetworking'] = True
    plist.write_bytes(plistlib.dumps(info))
    for language, name in [('en', 'Yukio'), ('zh-Hans', '雪绪')]:
        folder=resources/(language+'.lproj');folder.mkdir(exist_ok=True)
        (folder/'InfoPlist.strings').write_text('"CFBundleDisplayName" = "'+name+'";\n"CFBundleName" = "'+name+'";\n')
    subprocess.run(['codesign', '--force', '--sign', '-', str(app)], check=True)
    subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)
    assert all(digest(resources / name) == sha for name, sha in before.items())
    assert files(workbench_app / 'Contents/Resources') == workbench, 'Workbench input changed while packaging'
    archive = output / (f'Yukio-{version}-macOS-arm64.zip' if version else 'Yukio-Mac-0.4.6-chat-navigation.zip')
    subprocess.run(['ditto', '-c', '-k', '--norsrc', '--keepParent', str(app), str(archive)], check=True)
    result = dict(app=str(app), archive=str(archive), archive_sha256=digest(archive),
                  macos='arm64, macOS 13+', player_version=f"{info['CFBundleShortVersionString']} ({info['CFBundleVersion']})",
                  workbench_version=workbench_version, original_resources_preserved=len(before),
                  sources=sources, files=files(app), baseline_resources=before,
                  signature='ad_hoc_not_notarized', github_published=False, windows='deferred_optional_by_user')
    (output / 'build.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return {k: v for k, v in result.items() if k not in ('sources', 'files', 'baseline_resources')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('base-app', 'workbench-app', 'binary', 'source', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    for name in ('version', 'build-number', 'source-revision'):
        parser.add_argument('--' + name)
    a = parser.parse_args()
    print(json.dumps(build(a.base_app.resolve(), a.workbench_app.resolve(), a.binary.resolve(), a.source.resolve(), a.out.resolve(), a.version, a.build_number, a.source_revision), ensure_ascii=False))
