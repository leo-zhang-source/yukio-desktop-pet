# 当前 Mac 依赖与模块边界

2026-11-01。版本以 `scripts/macos-release.json`、`scripts/macos-build-requirements.txt` 和 `YukioPlayer/Package.resolved` 为准；本轮没有升级依赖。构建入口、系统范围与校验方式见 [Mac 构建](MAC-BUILD.md)。

| 依赖 | 锁定版本 | 用途与类别 | 来源与许可记录 |
| --- | --- | --- | --- |
| Sparkle | 2.10.0 | App 内更新框架；运行时随包 | Swift Package 锁定官方仓库，框架内保留许可 |
| CPython | 3.12.14 | 工作台内置运行时；用户不用另装 Python | Astral python-build-standalone 官方归档及 SHA256；包内 `PYTHON-LICENSE.txt` |
| PyInstaller | 6.22.3 | 构建时冻结工作台；bootloader 随包 | PyPI wheel 固定哈希；GPLv2-or-later 与发行例外，保留 THIRD-PARTY-NOTICES |
| pyinstaller-hooks-contrib | 2026.9 | 构建时模块收集 | PyPI wheel 固定哈希；许可原文随构建依赖保留，不以缺失 metadata 字段推断无许可 |
| altgraph / macholib | 0.17.5 / 1.16.4 | 构建依赖分析、Mach-O 检查 | PyPI 固定哈希；MIT |
| packaging / setuptools | 26.3 / 84.2.1 | 构建环境与版本处理 | PyPI 固定哈希；Apache-2.0 OR BSD-2-Clause / MIT |
| Pillow | 12.3.0 | 构建图标及无损分页校验 | PyPI 固定 arm64 wheel 哈希；MIT-CMU |
| dmgbuild / ds-store / mac-alias | 1.6.5 / 1.3.1 / 2.2.2 | 构建磁盘镜像与 Finder 布局 | PyPI 固定哈希；New BSD / MIT / MIT |
| AppKit / SwiftUI / WebKit / SQLite / Foundation | macOS 系统组件 | 原生窗口、工作台嵌入、只读数据及文件解析 | 系统 SDK；最低系统声明 macOS 13，低版本实机仍待验 |
| Codex / Claude Code | 使用者自行安装 | 可选解释与活动来源；不捆绑账号或客户端 | 公开安装说明见 [Agent 说明](../EXPLANATION-AGENTS.md)；独立记录实际测试版本 |

依赖许可描述来自已核验构建的安装元数据和随包原文，不替代各依赖完整条款。项目根目录暂无统一项目许可文件，构建不捏造授权。没有“无第三方依赖”的前提。

## 模块职责

- `YukioCore`：日志协议、结果身份、状态路由、问题展示状态、动画时间；不发送聊天或操作 UI。
- `YukioPlayer`：macOS 窗口、输入焦点、传输桥接和自有后台进程生命周期；UI 更新在主线程。
- `tools/activity-workbench`：本机记录、只读查询、解释预览与逐用户授权。每个使用者使用自己的账号／服务。
- `scripts/build-macos.py`：只从指定提交导出、构建与核对完整候选包；不会发布或替换现用 App。
- `tests/remediation`：人工共同样例、错误探针、输入诊断、负载测试；不能代替独立环境实际包验收。

可选模型不可用时仍可查看本机记录。NAS、作者开发目录和主机登录状态只用于开发证据保存，不能成为产品依赖。
