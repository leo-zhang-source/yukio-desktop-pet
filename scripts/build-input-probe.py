#!/usr/bin/env python3
"""Build a developer-only native input probe; never install or replace Yukio."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import plistlib
import subprocess

ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True,help='New directory for this probe build')
    args=parser.parse_args()
    if platform.system()!='Darwin':parser.error('This diagnostic is Mac-only; Windows is deferred')
    out=args.out.expanduser().resolve();out.mkdir(parents=True,exist_ok=False)
    package=ROOT/'YukioPlayer'
    subprocess.run(['swift','build','--package-path',str(package)],check=True)
    build=Path(subprocess.check_output(['swift','build','--package-path',str(package),'--show-bin-path'],text=True).strip())
    sources=[ROOT/'tests/remediation/native-input-probe/main.swift']+[
        package/'Sources/YukioPlayer'/n for n in ['QuestionPanel.swift','QuestionCard.swift','StatusBubble.swift']]
    app=out/'YukioInputProbe.app';exe=app/'Contents/MacOS/YukioInputProbe';exe.parent.mkdir(parents=True)
    info=dict(CFBundleIdentifier='org.yukio.remediation.input-probe',CFBundleName='YukioInputProbe',
              CFBundleExecutable='YukioInputProbe',CFBundlePackageType='APPL',NSPrincipalClass='NSApplication',
              LSUIElement=True,NSHighResolutionCapable=True)
    (app/'Contents/Info.plist').write_bytes(plistlib.dumps(info))
    objects=sorted((build/'YukioCore.build').glob('*.o'))
    if not objects:raise RuntimeError('The built YukioCore objects are missing')
    subprocess.run(['swiftc','-I',str(build/'Modules')]+list(map(str,sources+objects))+['-o',str(exe)],check=True)
    manifest=dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                  source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
                  executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
                  independent_installation_acceptance=False)
    (out/'build-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(app)
if __name__=='__main__':main()
