# 当前开发与发布入口

5.4 Preview 1（构建 55）使用 `codex/host-agent-integration` 的现用工作台产品线，保留界面与历史功能；本次发布整理在 `codex/mac-54-preview-release`，向 GitHub `main` 集成。包、更新源与实际运行核对见[交付记录](docs/remediation/RELEASE-54-PREVIEW1.md)。

[快速上手](docs/MAC-USER-GUIDE.zh-CN.md) · [English](docs/MAC-USER-GUIDE.md) · [完整 Mac 构建](docs/remediation/MAC-BUILD.md) · [开发约定](AGENTS.md)

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
