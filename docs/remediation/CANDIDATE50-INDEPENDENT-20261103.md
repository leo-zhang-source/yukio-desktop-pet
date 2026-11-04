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

通过 VM Safari 官方下载页取得 Claude 桌面 4.16336.0；签名为 Anthropic PBC（Q6L2SF6YDW），附带公证票据，严格签名验证通过。VM 的“仅 App Store”策略阻止启动；已请求仅为该 App 添加“Open Anyway”例外的当次确认，尚未执行。不能用已登录的 Claude Code CLI 替代桌面 Code／Cowork。

## 归档恢复

另一聊天按协调完成候选 49 固定产物的 NAS 归档：`nas:/volume1/leo/yukio-validation/2026-11-03/candidate49-restore-20261104T015155Z`。18 文件共 233,108,923 字节，远端 SHA-256 与回读一致；源码恢复 2519 项、App 恢复 490 项一致，strict codesign 通过。没有包含凭据或正在变化的新证据，也未删除原件。

候选 49 回执位于本机 `yukio-agent-setup/20261103-nas-candidate49/receipt.json`。本聊天另将候选 50 固定集合保存到 `nas:/volume1/leo/yukio-validation/2026-11-03/candidate50-restore-20261104T022144Z`：11 文件共 233,311,619 字节，远端与回读哈希一致；源码恢复 2521 项、实际 App 恢复 490 项一致，strict codesign 通过，未发现私人配置，未删除原件。候选 50 回执在本轮私有根目录 `candidate50-nas/receipt.json`。

两份回执只证明各自 manifest 中的固定集合恢复成功，不包含之后新增的测试。历史“NAS 连接超时”描述保留为当时情况。

## 证据与待验范围

私有根目录：`/Users/leozhang/.codex/backups/yukio-stage1-5/20261101T185459Z/`。包括 `vm49-20261103-before-source-fix.json`、`vm49-20261103-source-identity.json`、`vm49-20261103-authorization-rebound.json`、授权界面截图与 `candidate50-checks/`。原始聊天与账号数据不加入源码。

实际包证据包括 `vm50-package.json`、`vm50-source-fix-installed.json`、`vm50-source-fix-post-reboot.json`、`vm50-system-reboot-boot-times.json`、`vm50-active-before-normal-quit.json`、`vm50-active-after-normal-quit.json`、`vm50-resume-A2-result.json`、`vm50-history-after-continuation.json` 和两张实际界面截图。`vm50-claude-source-line-check-corrected.json` 按产品规则排除行尾换行进行校验；初次诊断误把换行算入哈希，不代表产品数据损坏。

当前授权证据为 `vm50-accessibility-exact-path.json` 与 `vm50-accessibility-enabled.png`，晚于固定 NAS 集合中的摘要；该摘要保留归档时的待验状态，后续授权结果以本段为准。

待补桌面 Code／Cowork、准确可见会话与通知、真实问题卡及中文输入法、父子任务、剩余并发矩阵、最低系统／Intel／多屏与独立升级异常路径。公开签名／公证、更新源发布及云端合并门槛未完成；没有取得 GitHub 写入授权。持续交互 30 分钟不得用构建或等待时间充数。
