#!/usr/bin/env python3
"""Build the standalone Windows workbench using the reviewed portable sources.

Run on Windows with PyInstaller installed in an isolated build environment.
No history, model configuration, or user transcript is copied into the package.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from build_bundle import build


def build_windows(destination):
    if sys.platform != 'win32':
        raise ValueError('Build the Windows executable on Windows')
    result = build(destination)
    package = destination / 'Yukio-Activity-Workbench'
    manifest = json.loads((package / 'MANIFEST.json').read_text(encoding='utf-8'))
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir',
               '--name', 'YukioWorkbench', '--distpath', str(destination / 'windows'),
               '--workpath', str(destination / 'build'), '--specpath', str(destination),
               '--paths', str(package / 'core'), '--noupx']
    for name in manifest['files']:
        path = Path(name)
        if path.suffix == '.py' or path.parts[0] == 'dist':
            command += ['--add-data', str(package / path) + ';' + str(path.parent)]
        if path.parts[0] == 'core' and path.suffix == '.py' and path.stem != '__init__':
            command += ['--hidden-import', 'yukio.' + path.stem]
    command.append(str(package / 'launcher.py'))
    subprocess.run(command, check=True)
    folder = destination / 'windows/YukioWorkbench'
    (folder / 'Start Yukio.cmd').write_text('@echo off\r\ncd /d "%~dp0"\r\n"%~dp0YukioWorkbench.exe" --collect\r\nif errorlevel 1 pause\r\n', encoding='ascii')
    (folder / 'README.txt').write_text(
        '雪绪活动工作台 Windows 试用版 0.2.9\n\n'
        '解压整个文件夹后，双击 Start Yukio.cmd。不需要另装 Python。\n'
        '首页选聊天，查看内容、解释、原因。第一次记录完成需要稍等片刻。\n'
        '关闭启动窗口会停止本次启动的记录器；历史保留，原桌宠不受影响。\n'
        '没有设置模型时仍可显示本机说明；真实聊天发送需要先看预览并同意。\n'
        '数据保存在 %LOCALAPPDATA%\\Yukio\\activity-observation。\n'
        '请保留 _internal 文件夹，它是程序的一部分。\n'
        '试用包未购买代码签名证书；如被系统安全提示拦下，请停下并核对来源，不关闭安全保护。\n', encoding='utf-8')
    shutil.copy2(package / 'MANIFEST.json', folder / 'SOURCE-MANIFEST.json')
    if (package / 'LICENSE').exists():shutil.copy2(package / 'LICENSE', folder / 'LICENSE')
    files = {str(p.relative_to(folder)).replace('\\','/'): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(folder.rglob('*')) if p.is_file()}
    (folder / 'PACKAGE-MANIFEST.json').write_text(json.dumps(dict(version='0.2.9',files=files),indent=2)+'\n',encoding='utf-8')
    archive = destination / 'Yukio-Activity-Workbench-Windows-preview.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in folder.rglob('*'):
            if p.is_file():z.write(p,p.relative_to(folder.parent))
    result.update(windows_zip=str(archive),windows_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),windows_files=len(files))
    (destination / 'build.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True,type=Path)
    print(json.dumps(build_windows(parser.parse_args().out.resolve())))
