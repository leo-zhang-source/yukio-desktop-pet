# 当前集中交付（2026-11-11）

用户本次明确要求整理全部更新并推送 GitHub。按第五阶段维护计划，Mac 5.4 Preview 3（63）／工作台 0.4.14 已发布，产品源码 `d7ae5cb9af57cd4db887ede55ea5e91126fc9d77`，汇集维护机制与 57–62 版修复，补充 Python 3.12.16 安全更新。最终产品两遍检查每遍 728 项测试与 230 条共享断言通过；6 个附件匿名下载验签完成，桌面已从公开包更新并启动，旧版与用户配置保留。源码、双语文档与签名预览源集中同步 `leo-zhang-source/yukio-desktop-pet` 的 `main` 与 `codex/stage5-maintenance`；具体证据、远端状态与 NAS 归档见[集中交付记录](docs/remediation/RELEASE-54-PREVIEW3.md)。完整独立首次使用验收仍暂停；Windows／云端 Cowork 仍暂缓。下面各次“仅本地／不上传”描述保留为当时记录，本次上传以新记录为准；下一次修改仍需新的明确上传授权。

# 当前修复（2026-11-11，Codex 解释，本地）

已本地更新并启动 5.4（62）／工作台 0.4.14，产品源码 `e64ac1294caa7956a68a238de0e200e4b36c0541`。修复来源选择未保存及 Codex 继承最高推理强度后超过 90 秒的问题；选择即保存，短解释只在子进程中限制较高推理强度，不改全局模型／账号配置。两遍完整检查每遍 728 项测试与 230 条共享断言通过；ZIP、DMG 与安装 App 的 495 个条目一致。包内真实 Codex 当前活动／工作解读分别 15.13／20.72 秒返回；已安装运行时的浏览器页面验证切换、重开保留和真实解释可见。61 版已完整备份，五份原配置及 Codex 全局配置不变。原生工作台点击自动化仍受工具限制；完整独立验收继续暂停，不上传 GitHub。详见[本轮记录](docs/remediation/CODEX-EXPLANATION-20261111.md)。

# 当前调整（2026-11-11，两级聊天列表，本地）

用户明确要求“Claude／Codex → 直接列出聊天”，主分类默认折叠，并隐藏没有可读内容的聊天。已本地更新并启动 5.4（61）／工作台 0.4.13，产品源码 `aaf7465ee3a35eefe4fcf71c32aee87340cfdb80`；两遍完整检查每遍 721 项测试与 230 条共享断言通过，ZIP／DMG／安装 App 的 495 个条目一致。60 版完整备份、五份原配置哈希不变。已安装工作台在浏览器中实际核对默认折叠、展开、搜索恢复和 Claude 聊天选择；原生工作台窗口自动操作受工具限制，未记为原生界面通过。见[本轮记录](docs/remediation/CHAT-TREE-20261111.md)。不上传 GitHub，独立首次使用验收继续暂停。

# 当前修复（2026-11-11，本地）

用户确认 Claude 中只有一个聊天，却被 58 版拆成多条。本轮直接核对 Claude 桌面客户端及其明确的当前／此前 CLI 记录关联，修复聊天身份、回退后的页面切换及要求栏残留的图片包装。已更新并从桌面入口启动 5.4（60）／工作台 0.4.12，产品源码 `1ca7d4c201b947448e73b9160f601390dd750a50`。完整检查两遍通过，每遍 711 项测试与 230 条共享断言；实际 ZIP／DMG／安装 App 的 495 个条目一致。桌面原生工作台中两个目标分别从五条／两条变为一条／一条，选择后对应 Claude 当前会话。58、59 版均完整备份，原配置保留。见[修复与归档记录](docs/remediation/CLAUDE-IDENTITY-20261111.md)。无 GitHub 上传；独立首次使用验收仍暂停，本机成功不代表通用交付通过。上轮“不同记录即不同聊天”的判断已由本次实际客户端证据纠正。

# 当前修复（2026-11-10，本地）

已在本地修复用户截图中的重复项目、Claude 聊天名称和解释原始标记问题，见[本轮记录](docs/remediation/CHAT-CLEANUP-20261110.md)。维护入口仍是此工作树 `codex/stage5-maintenance`；产品源码 `70915ebc0e30b83f2a6c7c8097ebbc203855da7d`，版本 5.4（58）／工作台 0.4.10。完整检查两遍通过，每遍 698 项测试与 230 项共享断言；实际 ZIP／DMG 与运行 App 的 493 个条目核对一致。用户随后明确要求“现在更新桌面雪绪，保留旧版备份”，已据此更新并启动桌面 App，保留旧版 56 的完整备份和原用户配置。未上传 GitHub；独立首次使用验收仍暂停，本机检查不代表通用交付验收完成。

# 当前维护入口（2026-11-07）

第五阶段 M0–M5 的本地机制已实施并验证，产品源码提交 `7cf565b2`，本地候选 5.4（57）。完整两遍检查与包核对已记录；M6 独立验收仍暂停。当前分支 `codex/stage5-maintenance`，基于实际 Preview 2（56）的 `2701916b`；保留其工作台与角色素材，只逐主题接入已核查修正。先读 [维护操作入口](docs/remediation/stage5-maintenance/README.md)、[实施记录](docs/remediation/stage5-maintenance/IMPLEMENTATION.md) 和 [范围/复核台账](maintenance/policy.json)。原整改线及桌面目录保留用于追溯。

11 月 7 日维护阶段只在本地保存、测试和准备候选，当时未替换正在运行的 App；11 月 10 日的本地替换按上节用户授权执行。**没有新的明确上传要求时，不上传 GitHub、不触发远端发布**。Windows/云端 Cowork 暂缓；完整独立首次使用验收仍暂停。隔离 HOME 的回归检查不等于独立用户验收。

随后用户明确要求的 [本地定时检查](docs/remediation/stage5-maintenance/SCHEDULED_CHECKS.md) 已启用，2026-11-08 按用户要求改为每 60 小时（两天半）检查一次，按周期追加依赖审计、回归和恢复演练；仅失败提醒。自动任务不升级、修复、发布或上传，周期和证据保存在仓库外。

Mac、Swift 6.1+、Python 3.12+、Node 22+ 是开发检查条件。先执行 `python3 scripts/maintenance.py check --out <仓库外的新目录>`；完整检查用 `python3 scripts/run-remediation-checks.py --repeat 2 --out <另一个新目录>`。本机默认 Python 3.9 不适用，可使用 `/opt/homebrew/bin/python3.13`。后续精确命令和失败处理见维护手册。

---

以下内容为历史交付与阶段记录，日期较早的当前入口、待批准和完成状态不覆盖上面的说明。

# 当前开发与发布入口

当前已发布 **5.4 Preview 2（构建 56）**：修复首次入口、助手就绪检查、空白页状态与安装窗口，保留现用工作台布局。[发布说明](docs/releases/5.4-preview.2.md) · [下载与实际运行核对](docs/remediation/RELEASE-54-PREVIEW2.md)。已集成至 GitHub `main`；整理分支为 `codex/mac-54-preview-release`。

[快速上手](docs/MAC-USER-GUIDE.zh-CN.md) · [English](docs/MAC-USER-GUIDE.md) · [完整 Mac 构建](docs/remediation/MAC-BUILD.md) · [开发约定](AGENTS.md)

首次使用验收按用户要求暂停：[干净 Mac 记录](docs/remediation/FIRST-RUN-20261104.md)。原公开包已完成下载、安装、系统放行和基础界面操作；修复包独立复验、助手登录与真实任务仍待验。本次仅按明确授权整理上传，不将待验项标为通过。

整改线候选 54 与现用工作台布局不同，未整体覆盖到本次发布；见[候选记录](docs/remediation/CANDIDATE54-INDEPENDENT-20261103.md)。Windows 与云端 Cowork 按用户要求暂缓。后续没有新的明确上传要求时继续只保存在本地。

---

以下保留历史开发快照，不是当前包版本或发布状态。

# 开发从这里开始

2026-10-31 账号迁移：新账号主线汇集到 `8d248f984f18` 的阶段 1～4 开发成果，并合并旧公开主线历史和最新 Mac 优先约定。长期本地集成入口仍为 `codex/remediation-baseline`。开始下一项工作前先看 `AGENTS.md`，再核对分支和工作区改动。5.4 (41) 已有候选包，但独立验收和正式发行尚未完成；迁移没有替换现用 App。详见 [迁移状态](docs/GITHUB-MIGRATION.md)。

**2026-10-29 用户调整平台范围：当前阶段及后续整改优先完成 Mac；Windows 的开发、适配、构建、实机测试和发布全部暂缓，作为大后期可选事项保留。Windows 不属于当前阶段 2、3、4 的必做项，不阻塞 Mac 验收与交付。** 现有源码、包、测试、问题与候选保留，汇总见 [Windows 后期可选事项](docs/remediation/WINDOWS-DEFERRED.md)；用户明确要求恢复后再安排，不自动恢复下载。Mac 的独立环境验收要求继续执行。

**2026-10-29 GitHub 节奏调整：日常开发、修复和文档先在本地积累，阶段性成果或大更新完整就绪后集中上传。** 先备齐并核验源码、README、说明、包与更新源，整理为少量清晰提交后集中交付；避免每个小改动都推送、开改 PR、发 Release 或更新进度页。保留本地过程记录与恢复点；未上传的成果明确记为“待集中上传”。用户明确要求立即单独处理时以当次要求为准。

| 要找什么 | 对应位置或版本 |
| --- | --- |
| 日常修改和检查 | 当前目录；`codex/remediation-baseline` |
| 本次公开主线起点 | `ab0b017dfe83eaef1a181b107fb15427e13d0793` |
| 保留下来的桌面功能来源 | 5.3.2（38），工作台 0.4.1；`be9aa07fd5afdd0b4f212102d7b331792da28ce5` |
| 当前候选源码检查点 | `8d2deb2f1752319e6cf5044d8eadd0cb8e74d8bc`；5.4 (41)，尚未通过完整独立验收 |
| 公开下载 | 仍为 Mac 5.3；Windows 下载暂停。本分支不是新发行版 |
| 旧代码、实验和资料 | 原目录或已验证备份，见[去向清单](docs/remediation/SOURCES.md)；收尾发现两处旧目录从原位置消失，已登记恢复来源 |
| 后续工作 | 按阶段 4 记录补齐独立用户验收、接收方说明、签名公证与新账号更新源；Windows 保留为后期可选 |

先在这里明确一个问题及验收动作，再做一个主题的改动；检查通过后可保留必要的本地小提交与恢复点，不逐次推送 GitHub。不要从旧目录整体复制覆盖这里。日后需要并行开发时，从已确认的集成提交另开任务分支，并把结果审查后带回这个入口。原来的旧主目录用于查历史、取证和恢复，不再作为本轮整改的构建来源。

阶段 1 曾在当时源码上通过 232 项 Swift、262 项工作台 Python、31 项网页逻辑检查。重复运行的方法分别是：在 `YukioPlayer` 中运行 `swift test --parallel`；在项目根目录运行 `python3 -m unittest discover -s tools/activity-workbench -p 'test_*.py' -v`；运行 `node --test tools/activity-workbench/test_glance_ui.cjs tools/activity-workbench/test_language_ui.cjs`。使用隔离测试配置和人工样例，避免操作真实聊天。具体环境、证据和边界见[阶段 1 记录](docs/remediation/STAGE1-BASELINE.md)。

正式候选构建入口现为 `scripts/build-macos.py`，见[完整 Mac 构建说明](docs/remediation/MAC-BUILD.md)。历史零散入口保留用于追溯，不能把单独运行旧脚本当作完整交付。当前构建入口仍包含旧账号更新地址；下一次发行必须与正式更新源一并核验。

阶段 2 的场景检查、阶段 3 的修复和阶段 4 的候选构建已有记录。最新本机回归的历史结果为 585 项，详见[阶段 4 交付记录](docs/remediation/STAGE4-DELIVERY.md)；该结果不能替代[独立用户要求](docs/remediation/PORTABILITY.md)。下一步从阶段 4 未完成项继续，不重新把阶段 1 说明当成当前状态，也不因此恢复 Windows 工作。

10 月 31 日新增的[独立 Mac 界面记录](docs/remediation/STAGE4-INDEPENDENT-20261031.md)已随迁移保留：基础界面检查取得证据，G4 仍未通过，正式发布边界不变。

## Development policies (English)

**Current focus (2026-10-29): complete the Mac version first.** Windows development, adaptation, packaging, native testing and releases are deferred to an optional late phase. Existing code and records remain preserved; resume only when explicitly requested by the user. Windows work does not block current Mac acceptance or delivery. Independent-environment testing remains required for Mac.

**GitHub update cadence:** accumulate small changes locally and publish reviewed milestones or major updates together. Avoid rapid repeated pushes, PR edits, releases and progress-page changes unless the user explicitly requests an immediate separate update.
