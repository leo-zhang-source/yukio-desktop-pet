#!/usr/bin/env python3
"""Build a data-free portable workbench runtime from explicit source files."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parent
RUNTIME=('chat_catalog.py','reading_view.py','page_explanation_policy.py','plain_language.py','task_summary.py','project_context.py','handoff_view.py','source_context.py','glance_view.py','glance_automation.py','server.py','history_view.py','context_view.py','explanation.py','runtime_identity.py','localization.py','collector_status.py','launcher.py','start-macos.command','start-windows.cmd')

def build(destination,macos=False):
    if destination.exists():raise ValueError('Use a new output directory')
    destination.mkdir(parents=True)
    package=destination/'Yukio-Activity-Workbench';package.mkdir()
    for name in RUNTIME:shutil.copy2(ROOT/name,package/name)
    shutil.copytree(ROOT/'dist',package/'dist')
    (package/'README.md').write_bytes('''# Yukio 活动工作台 · 本机试用版

这是独立活动工作台的便携源码目录，不会替换桌宠。本目录的脚本需要 Python 3.9 或更新版本。

Mac 独立 App 0.3.6 已内置运行环境：直接打开外层“雪绪活动工作台.app”，无需安装 Python。本目录的 start-macos.command 供使用源码的人运行。Windows 当前为之后的可选任务，不作为本次交付或验收范围。
也可运行 python3 launcher.py --collect，随后打开 http://127.0.0.1:8767/ 。

首页选择聊天名称，直接看“内容、解释、原因”。 点“深入解释”可展开当前工作的做法、前后联系、用途和限制；点“之前做了什么”按每次要求回顾，一次三段，每段先由千问简短总结，再按需深入查看。两处只发送有限公开摘录，共用模型次数上限。点“任务与交接小结”可看整体目标、之前进展、当前结果、后续安排和各助手回复；缺失与采用未知分别保留。详细操作和依据默认收起，需要查旧记录时再点“记录详情”。
打开工作台会检查并接续缺少的记录器，只保存必要元数据。聊天原文和能明确配对的读取返回短片段只在本机临时读取，不复制进历史库。

无需模型也能查看常见步骤的简短说明，推测会单独标注。在用户已明确设置自动说明的设备上，打开页面就解释当前所选聊天，并保持跟进；关闭页面停止后续发送。无变化不重复生成，至少间隔3分钟；接收位置和短摘录范围在折叠的“说明与隐私”中查看。该设置在本机绑定接收位置，不随包分发。
模型配置从本机应用数据目录读取，不包含在包里；没有模型也能看本机原文说明。过滤不能保证隐藏所有私人信息，请在使用前了解折叠的发送范围。

本机目录：Mac 为 ~/Library/Application Support/YukioPlayer/activity-observation，Windows 为 %LOCALAPPDATA%/Yukio/activity-observation。
可用 --data-dir 指定其他目录。python3 launcher.py --check 只检查准备情况。关闭启动窗口停止由它新启动的服务，不删除历史或停止其他入口已启动的记录器；没有新增开机自启。

限制：仅显示实际可读到的一段；原文件缺失或改变时不补猜。操作请求不等于执行成功，这一轮结束不等于整个任务已验收。助手自述与推测单独标注；不读取隐藏思考，不做自动偏题判断。具体实测范围见交付记录；此 Mac 预览版尚未完成 Apple 公证；Intel Mac、Windows 与多天使用另行验收。
'''.encode('utf-8'))
    core=ROOT/'core/yukio' if (ROOT/'core/yukio').is_dir() else ROOT.parents[1]/'YukioWin/yukio';target=package/'core/yukio';target.mkdir(parents=True)
    todo=['activity_collector_cli'];seen=set()
    while todo:
        name=todo.pop()
        if name in seen:continue
        seen.add(name);path=core/(name+'.py');shutil.copy2(path,target/path.name)
        for n in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(n,ast.ImportFrom) and n.level and n.module:
                dep=n.module.split('.')[0]
                if (core/(dep+'.py')).exists():todo.append(dep)
    (target/'__init__.py').write_bytes(b'"""Yukio headless activity observation components."""\n')
    license=ROOT.parents[1]/'LICENSE'
    if license.exists():shutil.copy2(license,package/'LICENSE')
    files={p.relative_to(package).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(package.rglob('*')) if p.is_file()}
    (package/'MANIFEST.json').write_text(json.dumps(dict(kind='review_candidate',private_data_included=False,python_required='3.9+',windows_native_verified=False,files=files),indent=2)+'\n')
    archive=destination/'Yukio-Activity-Workbench-preview.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in package.rglob('*'):
            if p.is_file():z.write(p,str(p.relative_to(destination)))
    result=dict(portable_zip=str(archive),zip_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),files=len(files))
    if macos:
        if sys.platform!='darwin':raise ValueError('macOS build needs macOS')
        app=destination/'Yukio Activity Workbench.app';contents=app/'Contents';(contents/'MacOS').mkdir(parents=True);(contents/'Resources').mkdir()
        shutil.copytree(package,contents/'Resources/workbench')
        with (contents/'Info.plist').open('wb') as f:plistlib.dump(dict(CFBundleExecutable='YukioWorkbench',CFBundleIdentifier='local.yukio.activity-workbench.preview',CFBundleName='Yukio Activity Workbench',CFBundleShortVersionString='0.3.6',CFBundleVersion='25',LSMinimumSystemVersion='13.0',NSHighResolutionCapable=True),f)
        subprocess.run(['swiftc',str(ROOT/'WorkbenchApp.swift'),'-o',str(contents/'MacOS/YukioWorkbench'),'-framework','AppKit'],check=True)
        subprocess.run(['codesign','--force','--sign','-',str(app)],check=True,capture_output=True)
        result.update(macos_app=str(app),macos_binary_sha256=hashlib.sha256((contents/'MacOS/YukioWorkbench').read_bytes()).hexdigest(),signature='local_ad_hoc_not_notarized')
    (destination/'build.json').write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True,type=Path);p.add_argument('--macos',action='store_true');a=p.parse_args();print(json.dumps(build(a.out,a.macos)))
