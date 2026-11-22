#!/usr/bin/env python3
"""Build an arm64 Mac preview with its own runtime and no user data.

Run in an isolated environment with PyInstaller. The Swift window starts the
frozen local service; it never fetches a model or copies the user's profile.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import plistlib
import shutil
import ssl
import subprocess
import sys
import zipfile
from build_bundle import ROOT, build

VERSION = '0.4.1'
BUILD = '30'


def build_macos(destination, version=VERSION, build_number=BUILD):
    if sys.platform != 'darwin' or platform.machine() != 'arm64':
        raise ValueError('Build this preview on an arm64 Mac')
    result = build(destination)
    package = destination / 'Yukio-Activity-Workbench'
    source_manifest = json.loads((package / 'MANIFEST.json').read_text())
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
               '--onedir', '--name', 'YukioRuntime', '--target-architecture', 'arm64',
               '--distpath', str(destination / 'runtime'), '--workpath', str(destination / 'pyinstaller'),
               '--specpath', str(destination), '--paths', str(package / 'core'), '--noupx']
    for name in source_manifest['files']:
        path = Path(name)
        if path.suffix == '.py' or path.parts[0] == 'dist':
            command += ['--add-data', str(package / path) + ':' + str(path.parent)]
        if path.parts[0] == 'core' and path.suffix == '.py' and path.stem != '__init__':
            command += ['--hidden-import', 'yukio.' + path.stem]
    # Preserve trust restrictions shipped with the chosen Python runtime. Some
    # distributions load a CA policy file next to ssl.py when creating a context.
    trust_policy = Path(ssl.__file__).with_name('codex-rejected-cas.pem')
    if trust_policy.is_file():
        command += ['--add-data', str(trust_policy) + ':.']
    command.append(str(package / 'launcher.py'))
    subprocess.run(command, check=True)
    # Execute the frozen entry outside the source tree before accepting the
    # build. Neither the author profile nor a development Python is available.
    check_home=destination/'runtime-check-home';check_home.mkdir()
    checked=subprocess.run([str(destination/'runtime/YukioRuntime/YukioRuntime'),
        '--check','--data-dir',str(check_home/'data')],cwd=check_home,
        env={'PATH':'/nonexistent','HOME':str(check_home),'CFFIXED_USER_HOME':str(check_home),
             'CODEX_HOME':str(check_home/'.codex'),'CLAUDE_CONFIG_DIR':str(check_home/'.claude'),
             'LANG':'en_US.UTF-8'},capture_output=True,text=True,timeout=30,check=True)
    readiness=json.loads(checked.stdout)
    if not readiness.get('collector_code_available') or any(c['available'] for c in readiness['clients']):
        raise ValueError('Frozen runtime readiness check failed')
    (destination/'runtime-check.json').write_text(json.dumps(readiness,indent=2)+'\n')
    app = destination / '雪绪活动工作台.app'
    contents = app / 'Contents'
    (contents / 'MacOS').mkdir(parents=True)
    resources = contents / 'Resources'
    resources.mkdir()
    shutil.copytree(package, resources / 'workbench')
    shutil.copy2(ROOT / 'THIRD-PARTY-NOTICES.txt', resources / 'THIRD-PARTY-NOTICES.txt')
    shutil.copytree(destination / 'runtime', resources / 'runtime', symlinks=True)
    with (contents / 'Info.plist').open('wb') as f:
        plistlib.dump(dict(CFBundleExecutable='YukioWorkbench',
            CFBundleIdentifier='local.yukio.activity-workbench.preview',
            CFBundleName='Yukio Activity Workbench', CFBundleShortVersionString=version,
            CFBundleVersion=build_number, LSMinimumSystemVersion='13.0',
            NSHighResolutionCapable=True), f)
    subprocess.run(['swiftc', str(ROOT / 'WorkbenchApp.swift'), '-o',
                    str(contents / 'MacOS/YukioWorkbench'), '-framework', 'AppKit', '-target', 'arm64-apple-macosx13.0'], check=True)
    subprocess.run(['codesign', '--force', '--deep', '--sign', '-', str(app)], check=True)
    subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)
    archive = destination / ('Yukio-Activity-Workbench-Mac-arm64-'+version+'.zip')
    # ditto preserves framework symlinks and executable bits. Drop Finder metadata.
    subprocess.run(['ditto', '-c', '-k', '--norsrc', '--keepParent', str(app), str(archive)], check=True)
    files = {p.relative_to(app).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(app.rglob('*')) if p.is_file()}
    result.update(version=version, mac_build=build_number, architecture='arm64',
                  python_required=False, minimum_macos='13.0', macos_app=str(app), macos_zip=str(archive),
                  macos_zip_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                  macos_files=files, signature='ad_hoc_not_notarized',
                  windows='deferred_optional_by_user')
    (destination / 'build.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    return result


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--version', default=VERSION)
    p.add_argument('--build-number', default=BUILD)
    a=p.parse_args()
    r=build_macos(a.out.resolve(), a.version, a.build_number)
    print(json.dumps({k:v for k,v in r.items() if k!='macos_files'},ensure_ascii=False))
