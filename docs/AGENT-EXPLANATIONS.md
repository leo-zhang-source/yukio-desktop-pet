# Agent explanations: implementation and evidence / Agent 解释实现与证据

Users: follow the **[English Mac guide](MAC-USER-GUIDE.md#explain)** or **[中文 Mac 指南](MAC-USER-GUIDE.zh-CN.md#explain)**. 5.4 Preview 1 uses the host 41.6 workbench and backend. The records below also describe a separate remediation line; its setup cards and UI are not in this package. / 5.4 Preview 1 采用本机 41.6 工作台与后台；下方部分记录属于另一条整改线，其设置卡片与界面不在本包中。

## Current behavior / 当前行为

- Local maintenance build 62 saves a provider selection immediately without changing whether explanations are enabled. Failed or busy changes explicitly retain the active selection. Codex's explicitly configured high or greater reasoning effort is capped at medium for each bounded explanation only; the user's model, account and global configuration stay intact. / 本地维护版 62 选择来源即保存，并保持解释开关；失败或忙碌时明确保留实际来源。Codex 明确设置的 high 及更高推理强度仅在本次短解释中限制为 medium，保留用户模型、账号及全局配置。见[本轮记录](remediation/CODEX-EXPLANATION-20261111.md)。
- Each user installs and signs in to their own Codex or Claude Code. Ordinary users see automatic selection, Codex and Claude Code; the author's private Qwen option is excluded from normal installations. / 每位用户使用自己的客户端与账号；普通安装只显示自动、Codex 和 Claude Code，不显示作者私人千问选项。
- Checks read client capabilities and sign-in status without generation. Automatic selection may try the other client before sending if readiness fails; an explicit selection or a failed generation does not silently switch services. / 检查不生成回答；自动模式可在发送前选择另一家已就绪助手，指定来源或实际调用失败不偷偷换服务。
- Explanations run independently, using bounded excerpts and the user's own account/service configuration. They do not continue or send messages to the source chat. Local records remain available on failure. / 解释独立运行，只使用有限摘录与用户自己的服务配置，不续接或发消息到原聊天；失败保留本机记录。
- Enabling automatic explanations is a user action. Closing the page stops further sends; already submitted requests may finish. With explanations enabled, expanding host workbench history groups can generate summaries on demand. / 自动解释需主动开启；关闭页面停止后续发送，已提交请求可能完成。启用解释后，展开本版历史分组可按需生成总结。
- Personal account data, private model options and explanation authorization are not shipped in the package. Windows work remains deferred. / 个人账号资料、私人模型开关与解释授权不进入包；Windows 继续暂缓。

## Evidence by version / 按版本查看证据

| Record | Scope / 范围 |
| --- | --- |
| [Early workbench 0.4.1 notes](history/user-guides-20261103/AGENT-EXPLANATIONS.md) | Historical protocol tests and then-missing real-service evidence. “Real generation unverified” applies to that snapshot. / 早期协议测试与当时未完成的真实调用，不代表后续候选状态。 |
| [Candidate 48 setup work](remediation/AGENT-SETUP-20261101.md) | Installation/sign-in cards, discovery and error handling; includes the later private-only Qwen change. / 安装登录卡片、发现和错误处理，含千问仅本机显示的后续改动。 |
| [Candidate 49 independent checks](remediation/CANDIDATE49-INDEPENDENT-20261101.md) | Both assistants' checks and real explanations in an independent Mac VM, within its recorded scope. / 独立 Mac VM 的两家检查与真实解释，结论限定于记录范围。 |
| [Candidate 50 independent checks](remediation/CANDIDATE50-INDEPENDENT-20261103.md) | Actual package, system reboot, old-history reading and chat continuation; not a clean first-install run. / 实际包、重启、旧历史与续跑，不是全新首次安装。 |

See the [acceptance limits](MAC-USER-GUIDE.md#verification) / [验收边界](MAC-USER-GUIDE.zh-CN.md#verification) before making delivery claims. Earlier client flags and test counts are retained in the historical notes, not presented as universal compatibility guarantees.

Current release lineage / 本次发布来源：[Host 41.6](remediation/HOST-AGENT-41.6.md) · [5.4 Preview 1](releases/5.4-preview.1.md).
