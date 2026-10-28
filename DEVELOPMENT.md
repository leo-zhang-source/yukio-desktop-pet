# 开发从这里开始

2026-10-27 阶段 1：本目录是整改工作的统一集成入口，分支为 `codex/remediation-baseline`。开始下一项工作前先看 `AGENTS.md`，再核对当前分支和工作区改动。本阶段整理源码来源、保留现有功能并建立检查基准，没有发布新版本。

| 要找什么 | 对应位置或版本 |
| --- | --- |
| 日常修改和检查 | 当前目录；`codex/remediation-baseline` |
| 本次公开主线起点 | `ab0b017dfe83eaef1a181b107fb15427e13d0793` |
| 保留下来的桌面功能来源 | 5.3.2（38），工作台 0.4.1；`be9aa07fd5afdd0b4f212102d7b331792da28ce5` |
| 可回到的产品源码检查点 | `964d5d61a025b68e04e6a0df55409352fe716b78`；其后的本阶段提交只增加开发说明与盘点记录 |
| 公开下载 | 仍为 Mac 5.3；Windows 下载暂停。本分支不是新发行版 |
| 旧代码、实验和资料 | 原目录或已验证备份，见[去向清单](docs/remediation/SOURCES.md)；收尾发现两处旧目录从原位置消失，已登记恢复来源 |
| 尚未接入的候选 | 5.3.3 的说明修正、工作台动态端口、Windows 小屏设置等，分别登记，保留原件 |

先在这里明确一个问题及验收动作，再做一个主题的改动；检查通过后保留一个小提交。不要从旧目录整体复制覆盖这里。日后需要并行开发时，从已确认的集成提交另开任务分支，并把结果审查后带回这个入口。原来的旧主目录用于查历史、取证和恢复，不再作为本轮整改的构建来源。

本阶段已经在当前源码上通过 232 项 Swift、262 项工作台 Python、31 项网页逻辑检查。重复运行的方法分别是：在 `YukioPlayer` 中运行 `swift test --parallel`；在项目根目录运行 `python3 -m unittest discover -s tools/activity-workbench -p 'test_*.py' -v`；运行 `node --test tools/activity-workbench/test_glance_ui.cjs tools/activity-workbench/test_language_ui.cjs`。使用隔离测试配置和人工样例，避免操作真实聊天。具体环境、证据和边界见[阶段 1 记录](docs/remediation/STAGE1-BASELINE.md)。

现在仍有多个旧打包入口：`YukioPlayer/scripts/build-app.sh` 只打播放器包，`tools/activity-workbench/build_macos.py` 打独立工作台，`build_integrated_macos.py` 组合多个输入。它们还没有形成可由新用户复现的统一发行流程，不能把运行某一个脚本当成完整交付。阶段 4 才整理并验收正式构建与安装；目前不得据此替换正在用的 App。

下一步是阶段 2：把[功能清单](docs/remediation/FEATURES.md)变成可重复的场景，补齐结果串号、真实输入和启动生命周期的检查。最终功能验收必须按[独立用户要求](docs/remediation/PORTABILITY.md)从真实安装包开始。
