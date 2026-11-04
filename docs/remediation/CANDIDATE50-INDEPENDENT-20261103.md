# 候选 50：继续独立 Mac 验收

2026-11-03（America/Los_Angeles；证据时钟 UTC 2026-11-04）。执行中，只保存在本地，未上传 GitHub、未替换主机 App。Windows 按用户决定暂缓。此前候选 49 的证据保留，不能直接作为候选 50 全部通过的结论。

## 本次发现与修复

恢复同一独立 VM 后，候选 49 的 8 张已有聊天卡全部报告来源不可读，实际转录文件仍存在。6 个 Codex 文件的 inode 未变，保存的设备号为 `16777234` 或 `16777231`，本次启动为 `16777230`。记录器本身已支持持久文件身份，但聊天列表和详情仍只比较启动期设备号与 inode；超过 24 小时的旧文件不会被新记录器重新扫描，因此问题不会自动消失。

候选 50 统一列表与详情的打开流程：对已打开的文件描述符检查卷 UUID、inode 与创建时间；双方均有持久身份时必须完全相等，否则保留严格的旧设备号／inode 检查。路径根目录、来源路径哈希、禁止符号链接、普通文件、来源代次、逐行内容哈希和读取上限继续生效。不会仅凭 inode 或标题认定为同一文件，也不为显示旧聊天改写历史库。

产品源码 `0ff54f2e9afbb6072a1b253580c70066276752ab`，5.4（50），工作台 0.5.5。新增 6 项检查覆盖 48 小时旧文件、新记录器零扫描、四聊天材料隔离、持久身份不符、缺少持久身份、旧格式严格回退、内容改写、同内容替换与符号链接。

## 已完成的自动检查

针对性 90 项通过。完整入口一轮通过：Swift 272、工作台 Python 327、发布 Python 13、Node 64、共用断言 230，均无跳过；两个故意错误均被拒绝，运行过程中源码指纹未改变。结果位于私有证据目录的 `candidate50-checks/summary.json`。这轮包含运行环境独立导出检查；实际包结果另列如下。

## 实际包、重启与续跑

- DMG：77,242,053 字节，SHA-256 `82b4a6a045aa5da48ba2eba1b1aa262b545678f6b7e8b536f34fb543fdad7d7b`；ZIP：76,829,721 字节，SHA-256 `def4b536418b19a7747abd62bfb4fe3edf7568402560a37d03003f189fdf5d15`。全部原始动画素材与候选 49 的构建输入一致。
- VM 只读挂载真实 DMG，复制到 `/Users/admin/yukio-qa-50/Yukio.app`，保留旧包。490 个文件／链接／执行权限与构建清单完全一致，strict codesign、原生与冻结环境 `--check` 均退出 0；未手工替换包内模块。仍为临时签名、未公证。
- 同一批 8 个旧聊天从候选 49 全部不可读恢复为列表与详情均可读。初始 Codex 214、Claude 82、Deep Code 0 条记录及 sources 保存点全部保持原样。Claude 每个聊天的两条超过 256 KiB 的未知记录继续受读取上限保护；逐行校验一致，没有通过放宽限制获得结果。
- 请求 VM 正常系统重启，启动时间确实改变；重新打开候选 50 后，8 个旧聊天仍可读，原 296 条与保存点完全一致，没有制造旧任务仍在工作的状态。此轮是系统重启后手工重开，不是自动登录启动测试。
- 使用真实 Codex CLI 0.165.0 续跑原 A 聊天。首次因测试目录不是 Git 仓库被 CLI 拒绝，失败证据保留；按 CLI 文档允许非 Git 测试目录后，以只读执行权限续跑成功。实际执行一次等待和一次预定打印，最终返回预定标记，exit 0。
- 在该真实任务运行时从菜单退出 Yukio，原生程序、工作台及 3 个记录器全部退出；外部 Codex 与其等待命令的 PID 和参数保持不变。重新打开 Yukio 后重新接上原活动，任务随后正常结束。实际工作台和角色分别观察到 Working 与本轮结束。
- 续跑新增 Codex 30 条，Claude 与 Deep Code 未增加；原记录逐行保持不变、所有 event_id 唯一、全部 source generation 不变。只有一项新的 turn_started 与 turn_ended，没有重新导入旧轮次。此结果不关闭所有 MC-05 延迟回执、重复来源、取消恢复场景。

## 独立环境及前置条件

继续使用原 Tart `yukio-fresh-macos`，macOS 26.6.2（25G83）arm64，独立系统磁盘与测试账号，已有前轮测试资料，不算新用户干净首次安装。此次宿主 macOS 27.2（26B123）arm64，VM 与宿主共用硬件和网络。

Tart 原生控制仍报告无窗口；通过 VM 已有 Screen Sharing 与仅绑定宿主回环地址的临时 noVNC 桥恢复界面操作。未开放公网端口，未修改主机辅助功能权限。

辅助功能列表中原同名 Yukio 条目对应旧包。通过 VM 系统设置移除旧条目、重新选取精确候选 49 路径后，最新原生诊断 `accessAllowed=true`，开始实际扫描窗口。仅证明权限已生效，不代表聊天识别和放牌场景已验收。

候选 50 使用新的临时签名，旧条目未自动适用。通过普通系统设置重新选择 `yukio-qa-50/Yukio.app` 后，UTC 02:27:12 的运行诊断为 `accessAllowed=true`，窗口扫描有效。首次路径输入仍选中旧包的失败记录保留，最终以精确文件夹选择和当前进程诊断为准。未编辑权限数据库或关闭系统保护。该现象属于临时签名候选的测试限制，正式签名升级后的权限延续仍待验。

通过 VM Safari 官方下载页取得 Claude 桌面 4.16336.0；签名为 Anthropic PBC（Q6L2SF6YDW），附带公证票据，严格签名验证通过。用户随后明确允许仅放行这个 Claude App，已从系统设置执行“Open Anyway”。全局“仅 App Store”策略保持不变，未移除 quarantine 或修改权限数据库。Claude 正常启动，运行位置为系统 AppTranslocation；主程序 SHA-256 与安装文件一致，不能因进程路径不是 `/Applications/Claude.app` 就判定未运行。

桌面端通过 VM 现有 Google 登录完成首次登录，没有复制宿主凭据。该账号界面显示 Free，Code 入口显示升级页面，没有购买方案。官方[桌面开始指南](https://code.claude.com/docs/en/desktop-quickstart)也说明该入口的方案要求；不能将 CLI 或 Console API 的可用性推定为桌面入口已可用。用户随后自行切换到已有可用账号并完成邮箱验证；登录期间停止界面操作。恢复后 Code 入口可用，实际测试如下。

UTC 02:49 的只读检查仍为 Codex 244、Claude 82、Deep Code 0 条，8 张旧卡保留。此时 Claude Code CLI 2.1.308 的 `auth status` 返回未登录；前轮成功调用的历史证据仍有效，但不能沿用为当前登录状态。桌面登录完成后须分别重检两种入口。相关证据：`vm50-claude-desktop-runtime-verified.json`、`vm50-claude-desktop-opened.png`、`vm50-claude-code-plan-gate.png`、`vm50-desktop-login-preflight.json`。早期按固定路径查进程得到空列表的记录保留，以 AppTranslocation 运行文件核验记录为准。

## Claude 桌面 Code 的真实双聊天

使用桌面 4.16336.0，在 VM 的 `desktop-code-A`、`desktop-code-B` 两个新目录分别放入无私人内容的 `QA.txt`。两个 Code 聊天在 This computer 运行；A 使用 Manual 模式，只批准一次 `/bin/sleep 60`，B 沿用新聊天的 Auto 默认，任务均明确禁止修改文件与访问其他目录或网站。A、B 均读取自己的标记并调用真实 AskUserQuestion；没有通过伪造转录制造状态。

- **YK-16 的活动接入：** 实际工作台出现两张独立 Claude 卡，并显示 Working 2；角色先跟随 A 的等待命令，随后显示 B 的问号牌。A 与 B 的本地会话编号、桌面 `local_` 编号能够分别关联。
- **YK-14 的误完成：** A 等待 ALPHA／BETA、B 等待 GAMMA／DELTA 时均未制造完成牌。直接在 Claude 回答 A 后，B 的问题与草稿仍保留。随后要求 A 只用一句普通回复询问 RED／BLUE 并停下，A 确实结束回复且仍待决定；工作台显示本轮结束，角色没有给 A 增加完成牌。原有 Codex 完成牌仍在，未被其他聊天清除。这是本次场景的通过，不代表已建立 Claude 整项任务完成协议。
- **YK-15 的身份识别：** 实际手动切换 A／B 后，原生诊断 `visibleSessions` 分别对应正确的本地会话编号；不是按标题猜测。系统通知出现时扫描暂不认定聊天可见，关闭通知后恢复。没有 Claude 完成牌产生，因此本轮不能据此宣布 Claude 的“看到完成聊天即放牌”全部通过；多屏与不同遮挡组合也未关闭。
- **真实问题卡失败路径：** 首次未配置回答通道，在 B 的 Yukio 问题卡发送测试草稿后明确提示需要连接通道。原稿保留，不重新点击输入框直接继续输入 `_AFTER_FAILURE` 成功；当时主窗口正在显示 A，草稿与错误仍属于 B。未将这次失败写成回答已送达。
- **公开配置入口：** 从 Yukio 菜单执行连接 Claude 后台回答，成功安装两个 hook；辅助程序哈希与候选 50 主程序一致，设置原先不存在。界面要求重启 Claude Code，旧问题不能因此被认为已接通。新连接后的真实发送结果与新发现列于下段。

新建 C 聊天实际调用 hook 后，第一次后台回答确实送达，但快速连发远程点击和键盘时，预期文本 `C_ONLY_REPLY_51` 的前四字进入 Claude 草稿，Yukio 实际提交并收到回执的是 `LY_REPLY_51`。保留焦点切换现场，不把完整预期输入判为通过；后续将点击聚焦与键盘输入分开核对。第二轮完整 `C_SECOND_EXACT` 已确认出现在 Yukio 输入框，发送仍误报需连接；同一时刻实际 hook 请求存在，未写入答案或回执。原因是 transcript 原始工具编号与 bridge 编号两路到达顺序不同，发送入口只接受后者。该真实缺陷进入候选 52，不将单次成功扩展为连续回答通过。候选 50 退出后 hook 正常回退到 Claude 自己的问题界面。

这轮同时发现需继续修复的状态问题：B 的 AskUserQuestion 已明确等待回答，原生角色正确，但工作台起初仍显示 working，超过新活动时限后变为 unknown；详情也相同。已保存修前原始元数据、接口和界面证据，作为 YK-16 的补充项进入候选 51。应从准确问题请求及其回执判断等待，不靠延长活动时限。

私有证据增加 `vm50-desktop-A-live-samples.jsonl`、`vm50-desktop-code-workbench-working2.png`、`vm50-desktop-code-A-manual-switch-native.json`、`vm50-desktop-code-B-after-notification-close.json`、`vm50-desktop-reply-ended-task-incomplete.png`、`vm50-desktop-question-failed-send-continued-typing.png`、`vm50-claude-answer-setup.json`、`vm50-desktop-plain-question-and-waiting-mismatch.json`。候选 51 前快照为 `vm50-before-candidate51.json`：Codex 244、Claude 227、Deep Code 0 条。Code 的新账号登录没有让独立 Claude CLI 自动登录，`vm50-new-account-cli-status.json` 仍报告未登录。

## 归档恢复

另一聊天按协调完成候选 49 固定产物的 NAS 归档：`nas:/volume1/leo/yukio-validation/2026-11-03/candidate49-restore-20261104T015155Z`。18 文件共 233,108,923 字节，远端 SHA-256 与回读一致；源码恢复 2519 项、App 恢复 490 项一致，strict codesign 通过。没有包含凭据或正在变化的新证据，也未删除原件。

候选 49 回执位于本机 `yukio-agent-setup/20261103-nas-candidate49/receipt.json`。本聊天另将候选 50 固定集合保存到 `nas:/volume1/leo/yukio-validation/2026-11-03/candidate50-restore-20261104T022144Z`：11 文件共 233,311,619 字节，远端与回读哈希一致；源码恢复 2521 项、实际 App 恢复 490 项一致，strict codesign 通过，未发现私人配置，未删除原件。候选 50 回执在本轮私有根目录 `candidate50-nas/receipt.json`。

两份回执只证明各自 manifest 中的固定集合恢复成功，不包含之后新增的测试。历史“NAS 连接超时”描述保留为当时情况。

## 证据与待验范围

私有根目录：`/Users/leozhang/.codex/backups/yukio-stage1-5/20261101T185459Z/`。包括 `vm49-20261103-before-source-fix.json`、`vm49-20261103-source-identity.json`、`vm49-20261103-authorization-rebound.json`、授权界面截图与 `candidate50-checks/`。原始聊天与账号数据不加入源码。

实际包证据包括 `vm50-package.json`、`vm50-source-fix-installed.json`、`vm50-source-fix-post-reboot.json`、`vm50-system-reboot-boot-times.json`、`vm50-active-before-normal-quit.json`、`vm50-active-after-normal-quit.json`、`vm50-resume-A2-result.json`、`vm50-history-after-continuation.json` 和两张实际界面截图。`vm50-claude-source-line-check-corrected.json` 按产品规则排除行尾换行进行校验；初次诊断误把换行算入哈希，不代表产品数据损坏。

当前授权证据为 `vm50-accessibility-exact-path.json` 与 `vm50-accessibility-enabled.png`，晚于固定 NAS 集合中的摘要；该摘要保留归档时的待验状态，后续授权结果以本段为准。

待补桌面 Code／Cowork、准确可见会话与通知、真实问题卡及中文输入法、父子任务、剩余并发矩阵、最低系统／Intel／多屏与独立升级异常路径。公开签名／公证、更新源发布及云端合并门槛未完成；没有取得 GitHub 写入授权。持续交互 30 分钟不得用构建或等待时间充数。
