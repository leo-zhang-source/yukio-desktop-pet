# 候选 49：独立 Mac 实际包验收

2026-11-01。本轮继续阶段 1–5 联合整改，已完成以下实际包检查；**未完成全部功能验收，不能宣布全部阶段关闭或公开交付**。Windows 按用户决定暂缓。

## 固定来源和环境

- 产品提交：`731ae1aadd53c2ad9c8c3a5be0ab69a3e2f271e0`；版本 5.4（49），工作台 0.5.4。后续验收文档提交不改变此包的产品源码。
- 实际 DMG：`Yukio-5.4-candidate-49-macOS-arm64.dmg`，77,243,168 字节，SHA-256 `a57542e228c66c1228a4930da05ef8e5abb5f7131bf944cfb67feac478f7c614`。
- ZIP：`Yukio-5.4-candidate-49-macOS-arm64.zip`，76,827,564 字节，SHA-256 `d9ae12b84be079e7ff75b154944eaa93f1731f0666160a47f1e2008495559b48`。
- 独立 Tart 虚拟机 `yukio-fresh-macos`，macOS 26.6.2（25G83）arm64，测试用户 admin；独立系统磁盘、数据、凭据，不复制主机账号或私人服务配置。共用宿主硬件与网络，已有前轮测试资料，**不是全新干净首次安装**。
- 实际 DMG 只读挂载并复制到测试目录，没有修改包、移除隔离属性或覆盖原安装。490 个文件／符号链接／执行权限与构建清单一致，strict codesign、原生 `--check`、冻结运行环境 `--check` 通过。无须在 VM 安装 Python 或 Swift。
- 临时签名，未公证；这不等于公开浏览器下载后的 Gatekeeper 首次打开通过。

## 实际结果

| 检查 | 结果与证据范围 |
| --- | --- |
| 两助手登录与检查 | Codex CLI 0.165.0、Claude Code 2.1.308。用户在 VM 官方页面完成 Claude 登录。实际桌面启动的包内服务与设置页的“检查安装与登录”均显示两家就绪。SSH 登录会话单独查询 Claude 时不可访问桌面登录凭据，不能据此判定桌面 App 未登录 |
| 普通用户助手选择 | 实际原生 WebKit 设置下拉列表仅有跟随聊天、Codex、Claude Code；与 API 三项一致，无千问选项。未借用作者内网服务 |
| 两种 Agent、四个真实聊天 | Codex A／B、Claude C／D，在四个独立测试目录并发，仅执行一次等待和一次打印。四路均正常返回预定结束文字，进程 exit 0；四张聊天卡与各自记录独立。根据来源事件四轮同时活跃约 18.873 秒；工具执行重叠约 0.963 秒。并发规模为四，不宣称无限并发 |
| 工作与结束状态 | 观察到 Claude 工具执行时原生角色工作、工作台列出活动；各聊天结束后详情为“本轮已结束”。原生最终完成牌仅包含 Codex 三条测试聊天，不包含 Claude C／D。CLI 证据不等于 Claude 桌面 Code／Cowork 验收 |
| Claude 工具关联 | 两条请求和对应返回保存在 `message_observed.blocks` 内，按 tool_use_id 关联成功；顶层没有独立 tool_result 行属于协议格式，不是回执丢失 |
| 两家真实解释 | 对新建的合成任务聊天分别预览并明确发送短摘录，Codex 28.88 秒、Claude 14.94 秒，均返回 `mode=model`。只证明这两次实际调用成功，不证明模型每句话均正确；原设置已恢复 |
| 解释时切换与停止 | 实际界面在 B 生成时切到 C，关闭自动解释；等待后仍显示 C 的本机材料，没有被 B 的迟到结果覆盖。设置恢复为 Codex、自动解释关闭。此处只覆盖一个切换／停止场景，不关闭整个 MC-07 |
| 单来源停顿 | 对核实身份的候选 Claude 记录进程发送 SIGSTOP；期间 Codex 新任务 E 正常执行、记录和结束，工作台仍可查询，Claude 记录器超过时限显示 stale。finally 恢复 SIGCONT 后 Claude 返回 waiting。不是退出账号、断网、数据库损坏或所有故障场景的替代 |
| 历史保留 | 初始 Codex 139 条逐行按 event_id 与全部字段比对，0 丢失、0 改写。最终 Codex 214 条（新增 75）、Claude 82 条、Deep Code 0 条。新增内容均为本轮测试；没有清空旧库 |
| 进程与设置 | 检查时只有本次 App 所属的 1 个工作台服务和 3 个记录器，无重复实例。启用／停止解释设置与页面一致。后续虚拟机恢复重启的历史完整性检查通过，正常退出、重启后的 App 操作与登录启动仍未完成 |

四路原始客户端输出、来源记录、实际包清单、真实解释预览与结果、故障隔离轮询及完整性摘要均保存在本轮私有证据目录。没有将账号、凭据或原始聊天输出加入源码。

## 仍需完成

1. **Claude 桌面 Code／Cowork（YK-14／15／16）**：VM 当前只有 Claude Code CLI；桌面 App 尚未安装／登录。不能将 CLI 结果扩大为原问题的关闭依据。没有本地可读转录的远端 Cowork 场景继续明确为未验证范围。
2. **可见聊天与放牌**：重启前实际候选诊断 `accessAllowed=false`，没有可靠可见会话。用户先报告无法操作 VM；恢复后已确认可以操作，辅助功能列表仍为 0 个授权。已请求用户只为 VM 候选 49 开启权限并启动候选；完成后须重新核验运行诊断，不能使用重启前的旧文件判断当前授权。没有修改主机权限。工作台里选择聊天不等于源客户端页面实际可见。多窗口、多屏、遮挡、同名聊天与快速切换继续待验。
3. **真实问题卡与中文输入法**：回答／批准／拒绝、至少 10 次切换重试、父子工具、旧回执与原生焦点组合仍待实际客户端验证。自动测试覆盖其状态机，不替代实机操作。
4. **持续交互与安装恢复**：至少 30 分钟实际交互、最低支持系统／Intel、多屏、正常退出与系统重启、独立升级中断／空间不足仍未完成。界面工具等待、构建时间、API 轮询不计为 30 分钟交互。
5. **远端与发行**：云端失败阻止合并尚未实际演练；需要用户明确 GitHub 上传授权。签名／公证与公开下载迁移仍未完成。公开更新源的迁移不能由本地新 URL 配置单独证明。
6. **NAS 归档**：收尾连接 `nas`（192.168.2.131:1529）超时，本轮最新证据尚未完成 NAS 传输和远端恢复演练。本地包、固定源码、日志与 Git 恢复资料保留；未删除无关资料。仅清理本轮新生成、可重建的 Swift／venv 构建缓存。

## 虚拟机冻结与恢复补充

用户报告无法操作 VM 后，确认 guest SSH 与工作台 API 仍正常响应，但屏幕时钟和原生可见性记录停在 UTC 2026-11-02 00:00。采样显示 WindowServer 主线程等待 Metal／IOGPU 提交，Yukio 主线程等待 QuartzCore，渲染队列进入 AppleParavirtGPU；这定位到当时的图形调用阻塞，尚不足以确定最初诱因。

先使用 SQLite 在线备份保存三库，`integrity_check` 均为 ok，再请求 guest 重启并通过 Tart 停止／重开原 VM。没有换虚拟磁盘、清空用户数据、改安全权限或启动另一份候选。重启后 Codex 214 条、Claude 82 条、Deep Code 0 条记录按 event_id 排序、全部字段摘要与恢复前完全一致。WindowServer 最新采样已回到正常事件等待，用户明确确认“虚拟机可以操作了”。

自动控制仍独立出现 `noWindowsAvailable`、ScreenCaptureKit -3811 和一次全屏切换超时；这与重启前 guest 图形阻塞分别记录。用户可操作不等于自动控制已恢复；短暂的启动画面也不作为第二次 guest 冻结的结论。恢复重启只证明此次数据保留，不能替代正常退出、开机启动、持续交互或所有重启场景验收。

## 证据索引与兼容交接

私有目录：`/Users/leozhang/.codex/backups/yukio-stage1-5/20261101T185459Z/`。

- 自动检查：`merged-49-checks/summary.json`，两轮各 Swift 272、工作台 Python 321、发布 Python 13、Node 64、共用断言 230，0 跳过；两种负例均被拒绝。
- 性能：`merged-49-performance/results.json`；本机人工负载与实际 VM 操作分别记录，不混称。
- 实际包：`candidate-49/build.json`、`vm49-package.json`。首次 tar 比较包含传输附加的 AppleDouble 项，诊断后使用 COPYFILE_DISABLE 重新比对，490 项一致；未改包内实际文件。
- 实测：`vm49-four-chats-summary.json`、`vm49-current-after-concurrency.json`、`vm49-real-explanations.json`、`vm49-ui-settings.json`、`vm49-source-isolation.json`、`vm49-final-state.json`。
- 冻结与恢复：`vm49-freeze-sample.txt`、`vm49-windowserver-freeze-sample.txt`、`vm49-windowserver-post-reboot-sample.txt`、`vm49-desktop-recovery-before.json`、`vm49-desktop-recovery-data-check.json`、三份 `vm49-*-pre-recovery.sqlite`；含独立 VM 恢复前后的实际数据证据，不进入源码。
- 保留与恢复：`pre-integration/`、`stages-1-5.bundle`、`protected-assets-final.json`、`nas-availability-and-cache-cleanup.json`。增量 bundle 依赖已有基线 `9227f812`，不声称为可独立恢复所有历史的完整仓库。

本地恢复校验 `LOCAL-RESTORE-VERIFIED.json`：固定产品源码归档 `source-731ae1aa.tar.gz`（78,297,990 字节，SHA-256 `1d675fa5c5e8a36f032ad0bae66d31038333937484c0ecd9ae06c91f1cbaf1b6`）2519 项与构建前源码清单完全一致；ZIP 解到新的独立目录后，490 项文件／权限／链接一致、strict codesign 通过。初次恢复脚本误用旧版系统 Python，缺少 file_digest，失败记录保留；改用已有 Python 3.12 后通过。仅证明本地恢复，不是 NAS 回读验收。

统一集成入口已安全快进到产品提交 `731ae1aa`。7 份原有未提交资料保持原哈希；旧阶段补丁与恢复 stash 保留，不能再次盲目应用。与“接入用户 Agent 解释功能”聊天同步实测结果，继续由本聊天独占 VM，避免同时操作。未向 GitHub 写入，未替换主机正在使用的 App。
