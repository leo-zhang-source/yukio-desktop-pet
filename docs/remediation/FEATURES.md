# 功能、来源与后续验收动作

状态仅使用“已验证／已知缺陷／未验证／实验保留”。本表的“已验证”会明确限定范围；代码存在、历史通过或本机单元测试通过都不等于普通用户安装后可用。下列功能均有保留位置，未因整理删除。

来源缩写：M = 公开 main `ab0b017d`；I = 已安装版来源 `be9aa07f`，已接入 `964d5d61`；O = 旧主目录与阶段 0 快照。所有路径相对相应来源仓库。Windows 下载当前暂停，表中保留 Windows 源码不代表恢复分发。

**2026-10-29 范围调整：当前验收动作只执行 Mac 部分。** 表中的 Windows 平台、源码和历史状态继续保留；Windows 专用及跨系统的 Windows 验收部分全部转为[大后期可选事项](WINDOWS-DEFERRED.md)，不占用当前 Mac 整改排期，也不阻塞 Mac 阶段完成。恢复前需用户明确要求。

| 功能 | 平台与来源 | 源码或资料入口 | 当前状态与保留方式 | 后续验收动作 |
| --- | --- | --- | --- | --- |
| Claude Code 活动跟随 | Mac / Windows，M→I | `YukioPlayer/Sources/YukioCore/AgentSources.swift`；`YukioWin/yukio/sources.py` | 未验证（本轮只做源码和自动检查）；原实现保留 | 新用户安装自己的客户端，生成活动、提问、完成事件；未安装时给出真实提示 |
| Codex 活动跟随与结果归属 | Mac / Windows，M→I | `YukioPlayer/Sources/YukioCore/CodexParsers.swift`；`YukioWin/yukio/parsers_codex.py` | 已知缺陷：交错结果可能串号；当前行为及候选均保留 | A、B 并发；A 失败、B 成功及乱序、取消、重启，不相互污染 |
| Deep Code 活动跟随 | Mac / Windows，M→I | 两平台的 Deep Code 解析入口 | 未验证（当前真实客户端链路）；保留 | 使用测试用户自己的客户端和记录目录；未安装、格式变化时保持可解释状态 |
| 选择聊天、气泡和卡片堆叠 | Mac / Windows，M→I | `ActivityRouter.swift`、`CardStack.swift`、`StatusBubble.swift`；对应 Windows 模块 | 未验证（本轮自动检查通过）；已有显示和选择逻辑保留 | 多聊天切换、固定跟随、长标题、展开收起；不能回答到其他聊天 |
| 问题输入与选项 | Mac / Windows，M→I | `QuestionCard.swift`、`QuestionPanel.swift`；`YukioWin/yukio/question.py` | 已知缺陷：用户报告偶发不能输入，尚未定位；保留完整实现 | 从其他 App 点入，中文输入法、粘贴、刷新、切换聊天后继续输入，再核对发送对象 |
| 批准／拒绝与后台回答 | Mac / Windows，M→I | `CodexAnswerClient.swift`、`ClaudeQuestionBridge.swift`、`SurfaceApprovalBridge.swift`；`YukioPlayer/Resources/BACKGROUND-ANSWERS.md` | 未验证（真实新用户端到端）；网页／插件覆盖仍为实验范围 | 自有接收端先核对同一请求；真实账号由用户操作；取消、断线、重复点击不得错发或重复允许 |
| Deep Code 单独回答入口 | Mac / Windows，M→I | `YukioPlayer/integrations/deepseek/`；后台回答说明 | 未验证；现有固定版本桥接保留 | 新用户自行安装公开依赖和模型配置；不覆盖已有入口；断线回到原流程 |
| 完成举牌、取消举牌 | Mac / Windows，M→I | `ActivityRouter.swift`、`main.swift`；`YukioWin/yukio/router.py` | 未验证（本机自动检查通过）；保留 | 完成、查看聊天、手动取消和不同聊天切换时状态一致 |
| 雪绪与千夏皮肤、12 状态及独立眨眼 | Mac / Windows 资源，M=I | `YukioPlayer/Resources/Assets/`、`sources/approved-animation-rig/`、`sources/qianxia-held/` | 已验证（仅素材保留和来源指纹）；没有重新生成 | 实际包切换皮肤，播放所有状态和眨眼，核对分页与原始素材；跨系统分别实测 |
| 拖动、拎起与摆动、位置记忆 | Mac / Windows，M→I | `HangSwing.swift`、`PetWindow.swift`；Windows `hang.py` | 未验证（本机自动检查通过）；保留当前动作 | 拖动、换屏、松手、退出重开；窗口可找回，素材接缝保持 |
| 大小与气泡缩放 | Mac / Windows，M→I | `ScaleSlider.swift`、`TaskBubbleScalingTests.swift`；Windows 设置和气泡 | 未验证（本机自动检查通过）；保留 | 50%–200%、不同显示缩放，文字、点击范围和皮肤同时正确 |
| 中英文切换 | Mac / Windows，M→I | 原生 L10n、工作台 `dist/en.json` | 未验证（本轮网页和原生逻辑通过）；保留 | 切换后原生控件、网页、失败提示一致；重启保存选择 |
| 待机隐身 | Mac / Windows，M→I | `IdleVisibilityTests.swift`、`YukioWin/tests/test_idle_visibility.py` | 未验证（本机自动检查通过）；保留 | 空闲隐藏，工作／提问／完成按规则恢复，设置入口仍可到达 |
| 设置单页总览 | Mac，`089d8dc1`→`5c747d94` | `SettingsPanel.swift`、`docs/SETTINGS-OVERVIEW.md` | 未验证（本轮保留且布局测试通过）；不回退为旧分页 | 宽／窄窗口、长标题、中英文，全部原开关可达且重启保留 |
| Windows 紧凑设置 | Windows，M；小屏候选 `7c7ca92d` | `YukioWin/yukio/pet_settings.py` | 未验证；当前实现与候选保留，转大后期可选 | 当前不执行；以后用户明确恢复，再验证 Windows 小屏与高缩放能触达底部控件 |
| 原生工作台打开、重连与退出 | Mac，I；候选 `ad4bc936` | `WorkbenchPanel.swift`、`tools/activity-workbench/launcher.py` | 已知缺陷：固定端口及启动状态边界；当前实现和修复候选分别保留 | 占用端口、旧进程、超时、重复打开、退出重开；不结束无关服务 |
| 活动记录、项目侧栏、搜索和历史 | Mac 集成工作台；跨平台工作台源码，I | `tools/activity-workbench/` 及其 `core/yukio` | 未验证（262 项后端检查通过）；工作台专用 core 保留 | 新用户自己的记录；缺失、超量、截断、重启不伪造历史，原资料不丢失 |
| 当前解释、深入解释、分段回顾与交接 | 工作台，I | `agent_explanation.py`、`explanation.py`、`glance_automation.py` 等 | 未验证（模拟协议通过，真实账号生成未完成）；保留选择与授权机制 | 用户安装并登录自己的客户端，先明确授权；未登录／超时／额度不足可理解，停用后不再调度 |
| 自选内网模型 | 工作台，I | `docs/activity-workbench-model-configuration.md` | 未验证；保留可选配置，不能视为公共默认服务 | 测试用户自行配置可获得的服务；作者千问、NAS或局域网不可成为运行前提；需鉴权的旧适配仍有边界 |
| 软件更新 | Mac；Windows 源码保留，M→I | `SoftwareUpdates.swift`、`docs/UPDATES.md` | 已知缺陷：用户报告失败，历史有成功记录；当前真实链路未重验 | 从真实旧公开包更新，验证下载、签名、拒绝坏包、版本一致、资料保留和失败恢复 |
| 登录启动、显隐、暂停、演示、复位和退出 | Mac / Windows，M→I | `LaunchAtLogin.swift`、`main.swift`；Windows `startup.py` | 未验证（本机相关检查通过）；原操作保留 | 干净系统用户逐一开关、重启／登录，退出后 owned 服务状态符合约定 |
| 旧独立助手页面与提醒资料 | 历史 Mac / Windows，M 及 O | `docs/ASSISTANT.md`、提醒相关源码 | 实验保留／已暂停入口；不擅自恢复旧界面，资料保留 | 若以后恢复入口，另列产品范围，并验证旧提醒可读取及退出边界 |
| 抛掷、撞墙、眩晕实验 | Mac / Windows 实验，O | `ThrowPhysics`、`sources/interaction-rig/`、interaction 素材及测试 | 实验保留；不纳入当前桌面基线、不删除 | 另行确认动作取舍后验收物理、蒙版、原动作与跨平台一致性 |

本阶段没有选择舍弃任何当前功能。如果后续发现用户正在使用的行为不在上述清单中，应先追加来源和保留方式，再讨论实现，不直接以公开 main 覆盖。
