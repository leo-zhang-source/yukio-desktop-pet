# 候选 51／52：Claude 桌面等待与连续回答

2026-11-03（America/Los_Angeles，证据 UTC 2026-11-04）。仅本地开发与验收，未上传 GitHub、未替换主机 App。Windows 按用户决定暂缓。沿用独立 Tart macOS 26.6.2（25G83）arm64 与用户自行登录的 Claude Desktop 4.16336.0；这是带前轮测试资料的独立 VM，不是全新首次安装。

## 候选 51：明确提问保持待答状态

真实 Code 聊天 B 的 AskUserQuestion 未回答，但候选 50 工作台先显示 working，超过 120 秒变为 unknown；原生问题牌正常。修复统一列表／详情的等待判断：同一来源、聊天和轮次内明确提问且没有对应回执时保持 waiting；回答、取消、新一轮、截断边界及失去来源时不沿用旧等待。歧义或无法关联的结果不猜测为待答。

产品 `0f745d84bc6edeee2f8b0aca4589751e855bd3f1`，5.4（51），工作台 0.5.6。新增 7 项后端回归，修前正确测试环境下 4 项失败，修后通过。完整入口一轮 Swift 272／Python 334／发布 13／Node 64／共用断言 230 通过，无跳过，故意错误被拒绝。之后对边界查询加上同一 80 行窗口下限，再跑完整 Python 334 项通过；不把此前整轮的源码指纹说成最终查询版本的指纹。

DMG 77,244,621 字节，SHA-256 `45ae224792f3e497a1734eaf69ad68aa0bf44390397603caddb18746d40e5c7b`；ZIP 76,834,090 字节，SHA-256 `cd6c25ef506a8a8faadc20382c7d2d0a68019e7c74544d9b158236921c3af149`。只读挂载 DMG 安装到 `/Users/admin/yukio-qa-51/Yukio.app`，490 项文件／链接／权限匹配，严格签名、原生与冻结环境检查通过。临时签名，未公证，未移除 quarantine。

实际 GUI 启动原生程序并从菜单打开工作台。B 等待 27 分钟、C 等待 11 分钟时，列表与详情均为 waiting，界面显示 Waiting 2／Working 0，A 保持本轮结束。旧 Codex 244、Claude 227、Deep Code 0 条逐行保持不变；C 的正常活动使当前 Claude 增至 285 条。这些是实际客户端记录，没有修改转录来制造状态。随后在 Claude 自己的问题界面回答 C，C 回到 inactive，而 B 仍为 waiting，未清除其他聊天的待答状态。候选 51 新临时签名未继承辅助功能授权，诊断为 false；此次等待验证不依赖该权限，不据此扩大可见聊天验收。

证据：`candidate51-checks/`、`candidate51-python-final.log`、`vm51-package.json`、`vm51-desktop-waiting-fixed.json`、`vm51-history-preserved.json`、`vm51-desktop-two-waiting.png`、`vm51-desktop-B-waiting-27min.png`。

## 候选 52：transcript 与回答 hook 的精确关联

候选 50 的 C 第二轮已有活跃 hook，但显示的原始 `tool_use_id` 被发送入口拒绝，误报需连接。候选 52 增加严格解析：provider、session、原始调用编号和完整问题必须一致且只有一个候选；多题按完整问题确定索引。只给仍运行的 hook 写入答案；已确认的同答案可核对回执，异答案不覆盖，歧义明确回到 Claude 回答。原始批准请求不使用此回退路径。

产品 `28e4e3c9`，5.4（52），工作台仍为 0.5.6。新增 6 项 Swift 回归：连续两轮和多题反向回答、同编号跨会话与来源隔离、歧义请求／题目、过期／已结束及批准拒绝、回执幂等与完整问题检查、在途答案不覆盖。6 项针对性通过；完整一轮 Swift 278／Python 334／发布 13／Node 64／共用断言 230 均通过，无跳过，两个故意错误被拒绝，源码指纹不变。DMG 77,245,104 字节，SHA-256 `9e1fa12d85478142665f6cfcc205d65ccc27f5a6336defad0ac2213125fb0f0e`；ZIP 76,835,481 字节，SHA-256 `3fa744ae4bcec245c4b2c7b49925cb59b0997ad3931df81ce0b66e7bd27b3413`。实际 DMG 安装到 `/Users/admin/yukio-qa-52/Yukio.app`，490 项清单与严格签名、组件检查通过。实际连续两轮均已通过：C 的两个不同 AskUserQuestion 请求分别收到 `C52_ROUND_ONE`、`C52_ROUND_TWO`，各自答案、回执和 Claude 最终回显完全一致，问题卡正常收起。第二轮发送时主窗口显示 B，发送后仍显示 B，未激活或切到 C；B 的 47 条原记录逐行不变，仍待答，C 回到 inactive。原 Codex 244／Claude 227／Deep Code 0 条全部保留，当前 Claude 331 条，event_id 全部唯一。第一次快速点击和打字丢前缀的自动化现场仍保留；本次分开聚焦后核对完整输入，不据此宣布中文输入法或全部焦点场景通过。

证据：`candidate52-checks/summary.json`、`vm52-package.json`、`vm52-answer-setup.json`、两轮 bridge before／after、`vm52-two-rounds-isolation.json`、`vm52-two-rounds-received.png`、`vm52-round2-B-visible-C-answer.png` 与 `vm52-round2-B-preserved.png`。

## 尚未关闭的范围

后续通过系统设置把已有的 Yukio 辅助功能授权重新绑定到候选 52 的确切 App；运行诊断 `accessAllowed=true`。Claude 自身的辅助功能仍未开启。候选为临时签名，不能把这次手动重绑推广为正式签名升级也必然需要重绑。证据：`vm52-accessibility-exact-selection.png`、`vm52-accessibility-enabled.png`、`vm52-accessibility-rebound.json`。

新发现两个实际缺口，均不算通过：

- **旧待答问题重开后角色丢失。** B 未回答超过 50 分钟，工作台仍 waiting；候选 52 重开后原生只保留近期 C，虽然已识别 B 的确切桌面地址，却没有可匹配的 B 状态。根因为启动只回放最近 15 分钟与普通工具 30 分钟超时。`vm52-visible-B.json` 保存现场，后续候选单独修复验证。
- **新版云端 Cowork 未接入。** Claude Desktop 4.16336.0 的新界面中，实际创建专用 Cowork 测试，内置执行工具成功执行 `time.sleep(30)`，最后停在未回答的红／蓝选择；没有访问本机文件、网站或连接器。03:48:14–03:49:42 UTC 共 40 次样本里辅助功能均已授权，原生始终 idle、工作台仍是原 11 个聊天，没有这个云端会话。可见 URL 已被扫描到，但 URL 不能提供执行事件或任务完成依据。`vm52-cowork-result.json`、`vm52-cowork-samples.jsonl`、`vm52-cowork-execution-unanswered.png` 保存证据。当前来源读取本地 Claude Code 转录，不覆盖该云端执行；未误举牌不能在“完全未观测到任务”的情况下算作 YK-14 通过。

官方[新 Cowork 说明](https://support.claude.com/en/articles/13345190-get-started-with-claude-cowork)区分新的云端会话与本机能力。后续须为云端来源建立独立且可靠的身份／执行事件接入，再验证多会话和后台运行；不能套用本地 Code 已通过的结论，也不能用标题或回复措辞推测正在工作、等待或整项完成。

继续核对官方[架构说明](https://support.claude.com/en/articles/14479288-claude-cowork-architecture-overview)及[会话记录接口](https://platform.claude.com/docs/en/manage-claude/compliance-sessions)：个人方案的新会话默认云端执行，本地旧部署不能视作新账号的默认环境；列出的 Compliance API 面向 Enterprise，组织级 OpenTelemetry 由 Team／Enterprise 管理员配置。这些组织接口不能当成普通个人账号天然具备的依赖。本次未配置组织接口、读取登录令牌或用私有网页接口替代；当前尚未取得适合普通个人账号、可独立验收的后台云端事件来源。此项是明确的接入缺口，不能仅通过放宽空闲超时修好。

候选 50 的普通回复结束不误举完成牌、手动 A／B 精确识别等证据仍限其版本和场景。Claude 没有可靠整项任务完成协议，本轮不能仅凭回复结束生成完成牌，也不能凭可见身份正确宣布所有放牌场景通过。Cowork、完整 MC-01–08、中文输入法、父子关系、最低系统／Intel／多屏、完整异常升级与正式签名／公证／公开发布仍待验。30 分钟持续交互不以构建或等待时间计入。

私有证据根目录：`/Users/leozhang/.codex/backups/yukio-stage1-5/20261101T185459Z`。原始账号、聊天与凭据不加入源码；候选 51 固定 13 文件共 233,424,849 字节已保存至 `nas:/volume1/leo/yukio-validation/2026-11-03/candidate51-restore-20261104T032823Z`，远端与回读哈希一致，源码 2523 项、App 490 项恢复匹配，严格签名通过；未删除原件。候选 52 的固定 18 文件共 233,439,467 字节已保存至 `nas:/volume1/leo/yukio-validation/2026-11-03/candidate52-restore-20261104T033605Z`，远端与回读哈希一致，源码 2524 项、App 490 项恢复匹配，严格签名通过。两份清单仅覆盖各自固定集合，不自动包含之后的检查。
