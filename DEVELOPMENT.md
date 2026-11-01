# 开发从这里开始

**GitHub 上传要求（2026-10-31）：只有用户明确说“更新上传”或要求上传 GitHub 时才执行；其余工作默认只保存在本地，阶段完成也不自动上传。上传前告知目标与范围，结束后报告结果和链接；已明确授权的当次范围不重复询问确认。** 具体约定见 [AGENTS.md](AGENTS.md)。

## 2026-11-01 阶段 1–5 联合整改

统一集成入口仍为 `codex/remediation-baseline`。本轮在 `codex/stages-1-5-validation` 隔离检查，合入助手设置提交 `096e479b` 与普通用户隐藏千问选项的 `3808757b`；待测试证据固定后再回到统一入口。当前进度和未验收项见 [阶段总记录](docs/remediation/STAGES-1-5-20261101.md)。

完整自动检查从仓库根目录执行 `python3 scripts/run-remediation-checks.py --repeat 2 --out <新的证据目录>`，需要 Mac、Swift 6.1+、Python 3.12+、Node 22+。原生 UI 测试必须串行。正式构建只用 [Mac 构建入口](docs/remediation/MAC-BUILD.md)；模块与依赖见 [依赖记录](docs/remediation/DEPENDENCIES.md)，小任务使用 [任务卡](docs/remediation/TASK-TEMPLATE.md)。历史测试数量不能当作本轮结果。

## 2026-10-31 第一轮问题修复（本地候选）

当前修复入口是 [第一轮记录](docs/remediation/ROUND1-20261031.md)，问题依据为 [待修复清单](docs/remediation/ISSUES-TO-FIX.md)。同源完整 Mac 构建入口为 [MAC-BUILD.md](docs/remediation/MAC-BUILD.md)；动态端口已在阶段 3 接入并有阶段 4 限定范围的独立测试。第一轮固定源码 `9f11b164` 的候选 5.4（43）、工作台 0.5.1 已构建并完成有限包内接口验证，完整独立输入／窗口验收未完成；本聊天未发布或替换现用 App。后续提交不能继承该候选结论。用户新增的完成牌与 Claude 活动问题见[第二轮状态计划](docs/remediation/ROUND2-STATUS-PLAN-20261031.md)。

第五阶段补充要求见 [多聊天与多 Agent 同时工作](docs/remediation/STAGE5-CONCURRENCY.md)：设置、问题卡、后台读取和解释整理均须覆盖并行场景。这也是当前状态修复的验收要求；文档已登记不代表功能已经实现或通过。

**下文保留阶段 1 的历史快照**：其中“下一步是阶段 2”“尚未接入”“未形成统一构建”等是当时状态，不是当前开发指令。阶段 4 与当前修复记录优先；旧记录不能扩大为新版全部通过。

2026-10-27 阶段 1：本目录是整改工作的统一集成入口，分支为 `codex/remediation-baseline`。开始下一项工作前先看 `AGENTS.md`，再核对当前分支和工作区改动。本阶段整理源码来源、保留现有功能并建立检查基准，没有发布新版本。

**2026-10-29 用户调整平台范围：当前阶段及后续整改优先完成 Mac；Windows 的开发、适配、构建、实机测试和发布全部暂缓，作为大后期可选事项保留。Windows 不属于当前阶段 2、3、4 的必做项，不阻塞 Mac 验收与交付。** 现有源码、包、测试、问题与候选保留，汇总见 [Windows 后期可选事项](docs/remediation/WINDOWS-DEFERRED.md)；用户明确要求恢复后再安排，不自动恢复下载。Mac 的独立环境验收要求继续执行。

**GitHub 节奏约定（2026-10-29，2026-10-31 补充上传权限）：日常改动与阶段成果先保存在本地，只有用户明确要求“更新上传”或上传 GitHub 时才集中上传。** 就绪、需要修复或阶段完成都不构成上传授权。源码、README、说明、包与更新源先统一准备并核验，获准后用少量清晰提交集中交付；上传前通知目标和范围，结束后报告结果，避免频繁改动远端。保留本地过程记录与恢复点，未上传成果注明“本地完成／待上传”。

| 要找什么 | 对应位置或版本 |
| --- | --- |
| 日常修改和检查 | 当前目录；`codex/remediation-baseline` |
| 本次公开主线起点 | `ab0b017dfe83eaef1a181b107fb15427e13d0793` |
| 保留下来的桌面功能来源 | 5.3.2（38），工作台 0.4.1；`be9aa07fd5afdd0b4f212102d7b331792da28ce5` |
| 可回到的产品源码检查点 | `964d5d61a025b68e04e6a0df55409352fe716b78`；其后的本阶段提交只增加开发说明与盘点记录 |
| 公开下载 | 仍为 Mac 5.3；Windows 下载暂停。本分支不是新发行版 |
| 旧代码、实验和资料 | 原目录或已验证备份，见[去向清单](docs/remediation/SOURCES.md)；收尾发现两处旧目录从原位置消失，已登记恢复来源 |
| 尚未接入的候选 | 5.3.3 的说明修正、工作台动态端口等继续按 Mac 范围审查；Windows 小屏设置等保留为大后期可选，不列入当前整改 |

先在这里明确一个问题及验收动作，再做一个主题的改动；检查通过后可保留必要的本地小提交与恢复点，不逐次推送 GitHub。不要从旧目录整体复制覆盖这里。日后需要并行开发时，从已确认的集成提交另开任务分支，并把结果审查后带回这个入口。原来的旧主目录用于查历史、取证和恢复，不再作为本轮整改的构建来源。

本阶段已经在当前源码上通过 232 项 Swift、262 项工作台 Python、31 项网页逻辑检查。重复运行的方法分别是：在 `YukioPlayer` 中运行 `swift test --parallel`；在项目根目录运行 `python3 -m unittest discover -s tools/activity-workbench -p 'test_*.py' -v`；运行 `node --test tools/activity-workbench/test_glance_ui.cjs tools/activity-workbench/test_language_ui.cjs`。使用隔离测试配置和人工样例，避免操作真实聊天。具体环境、证据和边界见[阶段 1 记录](docs/remediation/STAGE1-BASELINE.md)。

现在仍有多个旧打包入口：`YukioPlayer/scripts/build-app.sh` 只打播放器包，`tools/activity-workbench/build_macos.py` 打独立工作台，`build_integrated_macos.py` 组合多个输入。它们还没有形成可由新用户复现的统一发行流程，不能把运行某一个脚本当成完整交付。阶段 4 才整理并验收正式构建与安装；目前不得据此替换正在用的 App。

下一步是阶段 2：把[功能清单](docs/remediation/FEATURES.md)中的 Mac 功能变成可重复的场景，补齐结果串号、真实输入和启动生命周期的检查。阶段 3 的修复及阶段 4 的正式构建与安装同样按 Mac 范围推进；Windows 保留到大后期可选阶段。最终 Mac 功能验收必须按[独立用户要求](docs/remediation/PORTABILITY.md)从真实安装包开始。
