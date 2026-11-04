# Background answers on Mac / Mac 后台回答说明

[简体中文](#zh) · [English](#en)

<a id="zh"></a>
## 适用范围

本说明对应 5.4 Preview 1（55）的 Mac 后台回答入口。Windows 工作暂缓；旧 Windows 步骤保留在源码仓库的历史资料中。真实问题卡、中文输入法及所有客户端组合尚未完成独立验收。

**跟随活动、生成解释和回传回答是三种不同功能。** 登录 Codex／Claude Code 用于解释，不会自动建立问题回传连接。先在雪绪设置开启“在这儿回答问题”，保持雪绪运行并跟随对应助手。

## 连接自己的助手

| 来源 | 操作和限制 |
| --- | --- |
| GPT / Codex | 只有已有后台连接的本机聊天能接收。不同 App、CLI、网页和插件不保证共用连接，没有通用连接开关；未连接时到原聊天处理。 |
| Claude Code | 菜单栏小头像 →“连接 Claude 后台回答”，按提示完成后重启 Claude Code。支持 AskUserQuestion 和 PermissionRequest；普通 Claude 网页聊天不是此入口。 |
| DeepSeek / Deep Code | 需要 Node.js 22+、Git 和自己的 Deep Code 模型配置。菜单栏选择“安装 DeepSeek 回答适配器”，成功后用下面的专用入口启动新聊天。已在其他入口启动的聊天不会自动接管。 |
| 网页／浏览器插件 | 实验功能，仅支持可识别的真实问题／批准按钮，不能保证任意页面版本可用。无法可靠匹配时到原聊天处理。 |

Deep Code 的单独入口不覆盖原客户端。安装器从官方仓库固定版本构建；今后在终端这样启动需要回传的聊天：

```sh
"$HOME/Library/Application Support/YukioPlayer/deepseek-runtime/yukio-deepseek"
```

Claude 连接会备份并合并 `PreToolUse / AskUserQuestion` 和 `PermissionRequest` hooks，保留其他规则。默认设置文件是当前用户的 `~/.claude/settings.json`，也遵从 `CLAUDE_CONFIG_DIR`；备份在 `~/Library/Application Support/YukioPlayer`。没有对应 PermissionRequest 的其他独立权限提示不走此通道。雪绪退出或未连接时退回原助手流程，不会自动允许。每次连接等待最多约 9.5 分钟。

## 回答和批准

1. 先核对聊天名称和完整问题。单选点选项，多选选好后提交，文字输入后按回车或发送键。问题或选项不完整时到原聊天查看。
2. 批准申请先显示完整内容，再明确选择允许或拒绝。回车、关闭或“稍后处理”不自动批准；“允许一次”不会变成长期权限。发送前发现请求过期或改变会停止。
3. 小回答框支持 Command-V/C/X/A 和撤销。失败保留输入；若提示可能已发出但回执缺失，先看原聊天，避免重复发送。收到回执不保证后续任务成功。
4. 收起问题后可回原聊天继续处理。关闭“在这儿回答问题”可隐藏回答卡，回原聊天继续处理。演示不发送。

## 权限与常见问题

本机后台回答不要求辅助功能权限。识别当前可见聊天以自动放下完成牌、实验网页／插件方式才用到该权限：雪绪设置中的“自动放牌需要辅助功能权限…”会打开系统入口，在“隐私与安全性 → 辅助功能”选择实际运行的 Yukio。临时签名候选更换后可能需要重新选择准确 App；授权成功不保证聊天一定可识别，可手动“取消举牌”。无需因此开启完全磁盘访问或屏幕录制。

Claude 接不上：确认执行了连接、重启了 Claude Code，且它确实发出了支持的请求。Deep Code 接不上：确认使用上方专用入口，并检查 `~/Library/Application Support/YukioPlayer/deepseek-setup.log` 的安装错误。Codex 未连接：在原聊天回答，不向其他窗口盲发。网页识别不唯一或已有其他草稿时，停止并回原聊天操作。

连接设置属于当前使用者，不随包提供作者凭据。卸载 App 不会自动撤销原助手中的 hooks；如需清理，先备份，只移除明确属于 Yukio 的配置，不覆盖助手的全部设置。

<a id="en"></a>
## Scope

This help covers Mac background answers in 5.4 Preview 1 (55). Windows work is deferred; its older instructions remain in the source repository's historical records. Real question cards, Chinese input methods and all client combinations have not completed independent acceptance testing.

**Activity following, explanations and answer delivery are separate capabilities.** Signing in to Codex/Claude Code for explanations does not establish a return connection. Enable Answer here in Yukio settings, keep Yukio running and follow the relevant assistant.

## Connect your assistant

| Source | Setup and limits |
| --- | --- |
| GPT / Codex | Only local chats with an existing background connection can receive answers. Apps, CLI, websites and plugins do not necessarily share that connection. There is no universal connection switch; use the original chat when unconnected. |
| Claude Code | Menu-bar avatar → Connect Claude background answers, then restart Claude Code. Supports AskUserQuestion and PermissionRequest, not ordinary Claude web chats. |
| DeepSeek / Deep Code | Requires Node.js 22+, Git and your own Deep Code model configuration. Choose Install DeepSeek answer adapter in the menu bar, then launch new chats through the dedicated entry below. Existing chats from other launchers are not taken over. |
| Websites / browser plugins | Experimental. Requires recognizable real question/approval controls; not every page version is supported. Use the original chat when matching is unreliable. |

The separate Deep Code launcher does not replace your original client. Setup builds a pinned version from its official repository. Launch chats needing this connection in Terminal with:

```sh
"$HOME/Library/Application Support/YukioPlayer/deepseek-runtime/yukio-deepseek"
```

Claude setup backs up and merges `PreToolUse / AskUserQuestion` and `PermissionRequest` hooks, keeping other rules. The default settings file is your `~/.claude/settings.json`, respecting `CLAUDE_CONFIG_DIR`; backups are in `~/Library/Application Support/YukioPlayer`. Independent permission prompts without a corresponding PermissionRequest do not use this route. When Yukio is closed or unconnected, the original assistant flow remains; requests are not automatically allowed. A connection waits up to about 9.5 minutes.

## Answer and approve

1. Check the chat name and full question. Click a single-choice option, submit after making multiple selections, or type and press Return/the send control. Use the original chat when text or options are incomplete.
2. Approvals show the full request before an explicit allow/deny choice. Return, closing or postponing does not approve. Allow once does not grant permanent permission. Changed or expired requests stop before sending.
3. The answer field supports Command-V/C/X/A and Undo. Failed sends retain input. If delivery may have happened without acknowledgement, check the original chat before retrying. Acknowledgement does not guarantee later task success.
4. After dismissing a question, continue in the original chat. Turn off Answer here to hide the card and handle it in the original chat. Demo mode does not send.

## Permissions and troubleshooting

Native background answers do not require Accessibility. Visible-chat recognition for automatic lowering of completion signs, and experimental website/plugin interactions, do. In Yukio settings choose Auto-lower needs Accessibility, then select the actual running Yukio in System Settings → Privacy & Security → Accessibility. Replacing an ad-hoc-signed candidate may require selecting the exact App again. Permission does not guarantee recognition; you can Lower sign manually. This is not a reason to enable Full Disk Access or Screen Recording.

For Claude failures, confirm setup, restart Claude Code and verify it issued a supported request. For Deep Code, use the dedicated launcher and inspect installation errors in `~/Library/Application Support/YukioPlayer/deepseek-setup.log`. For unconnected Codex chats, answer in the original chat. If website matching is ambiguous or another draft exists, stop and use the original chat instead.

Connections belong to the current user; no author credentials are bundled. Uninstalling the App does not undo hooks in the original assistant. To remove them, back up settings and remove only entries clearly belonging to Yukio, not the entire assistant configuration.
