# Mac 5.4 Preview 3 · 集中交付

2026-11-11。用户明确要求整理所有更新并推送 GitHub，按第五阶段 M0–M5 维护计划执行；M6 独立验收继续暂停。

## 本次任务卡

- 问题：公开 main 停留在 Preview 2，维护机制及本地 57–62 版修复尚未集中交付。
- 范围：从实际维护工作树 `codex/stage5-maintenance` 整理源码、双语 README／指南、发行记录、Mac 包、签名预览源与本机实际 App；目标 `leo-zhang-source/yukio-desktop-pet` 的 main 和维护分支。
- 来源：公开基线 `2701916b9c471d34dc11ff421b27d90cbb801248`；整理起点 `576d0c9d3a27c8714d899b5a06b9a73bd3bbbae9`；现用 62 版产品源码 `e64ac1294caa7956a68a238de0e200e4b36c0541`。新包目标 5.4（63），工作台 0.4.14。
- 验收：维护登记与到期项、上传差异及私有资料审查、两遍完整检查、同提交构建、实际包／签名／匿名下载／运行版本一致；各项结果如实追加。
- 回退：保留 62 版完整 App；只替换应用，不用旧数据库覆盖新增记录。其他工作树和历史未提交资料保留。

## 更新归类

| 主题 | 来源与结果记录 |
| --- | --- |
| 维护门槛、问题卡、读取性能、依赖和恢复 | [第五阶段实施](stage5-maintenance/IMPLEMENTATION.md)、[测试记录](stage5-maintenance/TEST_RESULTS.md) |
| 聊天名称与可读解释 | [58 版](CHAT-CLEANUP-20261110.md) |
| Claude 回退记录身份及图片包装 | [60 版](CLAUDE-IDENTITY-20261111.md) |
| 助手 → 聊天两级列表 | [61 版](CHAT-TREE-20261111.md) |
| Codex 选择持久化与解释超时 | [62 版](CODEX-EXPLANATION-20261111.md) |
| Python 3.12.16 发行前安全更新 | [依赖复核](PREVIEW3-DEPENDENCIES-20261111.md) |

已核对原桌面目录及历史工作树状态；未核实源码、旧生成目录、私人数据和备份不因“全部更新”而整包上传。原本地小提交保存在本地恢复分支，公开版本使用汇总提交；不改写已发布历史。公开维护记录移除本地聊天标识，并对个人目录采用通用写法；旧版本含标识的本地提交不会推送。当前维护工作树在整理开始时干净。

## 本轮证据

产品源码固定为 [`d7ae5cb9af57cd4db887ede55ea5e91126fc9d77`](https://github.com/leo-zhang-source/yukio-desktop-pet/commit/d7ae5cb9af57cd4db887ede55ea5e91126fc9d77)，对应标签 `v5.4-preview.3`、5.4（63）／工作台 0.4.14。后续汇总证据和签名更新源的提交只更新文档与 feed，不改变包内产品。最终产品指纹为 `1272a5da6e3605fdc97f5f21f16bbdf1ae9c8654b4ab6b4e3deabac1e297c404`。

| 核对范围 | 实际结果 |
| --- | --- |
| 完整本机回归 | 最终产品提交重新运行两遍；每遍 Swift 266、工作台 Python 361、发布 Python 28、进度 Python 8、Node 65，共 728 项测试，另有 230 条共享断言；失败、跳过、todo 均为 0。两遍来源指纹不变，失败反例均被正确拒绝 |
| 本机环境 | macOS 27.2 arm64、Swift 6.1.2、Python 3.13.2、Node 25.8.0；包内实际 Python 3.12.16 另运行工作台 361 项测试通过 |
| 依赖 | 10 项固定 Python 依赖审计无已知发现；CPython／原生库另按[官方来源复核](PREVIEW3-DEPENDENCIES-20261111.md)，不能由 pip 审计推导全部依赖安全；官方 Actions 锁在线及离线核对通过 |
| 最终包 | 实际解包 ZIP、只读挂载 DMG，495 个 App 清单条目及签名一致；8 个原生二进制检查完成，269 个角色资源与原 62 版一致 |
| 包内工作台 | 隔离 HOME 且 PATH 不提供开发环境 Python／Node，实际冻结入口启动；三次服务重启核对解释来源保存及关闭状态。Codex／Claude 离线客户端核对接收方身份、预览、发送前复核和只生成一次，包含中文及空格路径；没有借用真实账号，也没有声明真实模型调用通过 |
| 公开下载 | 6 个 Release 附件均匿名重新下载，大小／SHA-256 与准备文件相同；下载 ZIP 解出全部 495 条目并验签，签名更新源与 ZIP 签名通过；公开指南、包外指南、App 内指南内容相同 |
| 本机实际 App | 从匿名下载 ZIP 安装到用户 Applications，经桌面现有入口启动；实际进程为 5.4（63），源码 d7ae5cb9，工作台 0.4.14，495 条目一致。五份配置及 Codex 全局配置启动后哈希保持；桌面别名仍指向实际 App |

机器可读摘要见 [preview3-validation.json](preview3-validation.json)。完整原始日志、首次失败及本机回退包保存在本机 `~/.codex/backups/yukio-preview3-publish-20261111/`，不是 App 的运行依赖。原生工作台 GUI 未作为本轮通过项，隔离 HOME 和离线客户端也不等于独立首次使用验收。

## GitHub 与下载

[5.4 Preview 3 发布页](https://github.com/leo-zhang-source/yukio-desktop-pet/releases/tag/v5.4-preview.3)保留为 prerelease，稳定版 latest 仍为 5.3。发布页提供 DMG、ZIP、SHA256SUMS.txt、签名 preview.xml、mac-guide.html 与 release-manifest.json。README、双语指南和本页随汇总提交同步 main 与维护分支；预览 feed 使用已经匿名下载、验签的相同字节，稳定 feed 不变。

| 包 | 字节数 | SHA-256 |
| --- | ---: | --- |
| `Yukio-5.4-preview.3-macOS-arm64.zip` | 76,902,195 | `6a199d5d713c9e175522246e02fddb1b0517f33d2df8e5a669d4de31885522a3` |
| `Yukio-5.4-preview.3-macOS-arm64.dmg` | 77,319,783 | `d61b487fee355b2e03139a469c906775895f1470d23585e487f94a02b0e96d3e` |

源码与首批交付记录已集中同步 main、`codex/stage5-maintenance` 至 `b3e0270bc11dae92c2bdb5cd08f06211a42a2448`；两分支、标签指向及 GitHub raw README／文档／feed 已回读核对。预览 feed SHA-256 为 `86918902162643b6298717a09046d6d24201e134c9352f4be6f2694c50b524f2`，回读后验签通过。

远端 [main 检查](https://github.com/leo-zhang-source/yukio-desktop-pet/actions/runs/43134512536)与[维护分支检查](https://github.com/leo-zhang-source/yukio-desktop-pet/actions/runs/43134511963)均通过。GitHub runner 为 macOS 15.8.2 arm64、Swift 6.1.2、Python 3.13.17、Node 22.23.4；每个任务各跑两遍，每遍 728 项测试与 230 条共享断言通过。两份原始 artifact 已下载，经证据校验器核对提交、源码指纹、日志和失败探针通过；来源指纹与实际发布产品完全相同。这是另一台 Mac 的源码回归，未安装公开包完成普通用户首次使用，不能替代暂停的 M6。

Actions 已启用，权限只允许锁文件中四个经过核对的完整 Action 提交；Windows 自动任务保持暂停。main 要求 `Mac and workbench baseline` 检查成功且分支保持最新，检查来源限定 GitHub Actions（App 15368），管理员同样受约束，禁止强制推送和删除。收尾文档先进入维护分支，通过相同检查后再同步受保护的 main，不绕过检查门槛。

GitHub 对四个锁定 Action 给出 Node 20 运行时弃用提示，实际强制使用 Node 24 且全部步骤通过。Action 主版本迁移保留为后续维护复核；这不影响工作台按 Node 22 的本轮实际测试结论。

[实际失败探针 PR #1](https://github.com/leo-zhang-source/yukio-desktop-pet/pull/1)只把测试分支中的一个依赖校验值故意设错，[Mac 任务](https://github.com/leo-zhang-source/yukio-desktop-pet/actions/runs/43134772972)在维护检查处按预期失败。该 PR 无冲突且不是草稿，GitHub 明确显示 `mergeStateStatus: BLOCKED`；未尝试合并，随后关闭 PR 并删除临时远端分支。main 和发布包未混入故意错误。该证据验证了真实失败会阻止合并，不只依赖保护规则的配置回读。

`maintenance/action-pins.json` 与本地维护命令中的 `remote_enforcement: not_enabled` 是产品冻结时的历史状态，不是实时 GitHub 查询。当前服务器权限、分支保护和实际运行以本页及机器摘要的远端证据为准。

## 回退与 NAS 归档

62 版完整 App 保存在本机上述证据目录的 `installed-before/Yukio.app.archived`，替换前的原 App 另保留为 `Yukio.app.retired`；只替换应用，未恢复旧数据库覆盖新记录。其他历史工作树和未提交资料保留，不将其整体合入公开版本。

NAS 在传输前确认可达、可写且容量充足。以下两份归档均已核对远端与回读 SHA-256，证据包另逐文件复原核对；没有删除本地原件。源码归档从已审查的产品树直接流式写入 NAS，不包含私人本地提交历史。

| 内容与路径 | 字节数 | SHA-256 |
| --- | ---: | --- |
| `nas:/volume1/leo/yukio/maintenance/preview3-20261111/source.tar.gz` | 78,539,571 | `39e754a7b0d824cf3609136c6a8fb707c3b2eb32b4f026b2b0103a25b152babe` |
| `nas:/volume1/leo/yukio/maintenance/preview3-20261111/evidence/evidence.tar.gz` | 153,737,183 | `84d3bd9c2ea37c823d05fd369b302252a78654a4e0c270514eb61eb252966675` |

证据归档显式选取 126 个文件，包含最终公开附件、构建／测试／下载／安装摘要、原始测试日志和首次失败。用户数据库、凭据、私人配置内容、旧版 App 和本地私人历史不进入公共附件。远端启用与最后一次 main 同步发生在该归档之后，单独保留收尾记录，不声称原归档已包含后续状态。

## 首次失败与处理

- 首次证据校验误在第二遍测试结束前启动，校验器拒绝不完整输出。两遍结束后使用新目录复验通过，首次失败保留。
- 旧 `check_agent_runtime.py` 有两处过期契约：返回名称仍固定为旧短名，调用序列也没有计入发送前再次核验同一接收方。逐次失败和诊断保留。已核对源码调用链，改为检查明确 provider、返回名称与预览接收方一致，并严格断言预览只有 help/auth、同意发送后再次 help/auth 且只生成一次；两家离线客户端实际复验通过。中途完整检查已停止并保留，不用于放行；最终修订后重新检查和构建。未使用真实账号，也没有取消身份、次数或内容断言。
- 整理前的候选和汇总后、检查器修复前的候选均只作本地证据；实际上传只用最终交付包。
- 首次远端任务提交时仓库关闭了 Actions，未实际启动；启用后，版本标签白名单拒绝了由 Actions 锁解析出的固定提交。已按核对过的四个完整提交设置精确白名单，保留启动失败记录并复跑，未放宽为任意 Action。
- 两次早期标签任务仍显示无 job 的 queued，GitHub 的取消／强制取消接口拒绝，分别表示任务或重跑尚未进入队列；没有把它们记为通过或已取消。后续分支 push 已实际分配 Mac runner，完整结果单独记录。
- 设置分支保护时 API 拒绝同时传入旧 `contexts` 与新 `checks` 字段；保留原请求，改为仅传明确来源的 `checks` 后配置与回读成功。未降低保护要求。

## 保留的限制

独立首次使用、真实多客户端完整验收及 30 分钟 GUI 性能仍按用户决定暂停。App 临时签名、未 Apple 公证；macOS 13 真机、Intel 和完整自动升级未验。Sparkle 2.10.1 需单独的升级路径验收。Windows 与云端 Cowork 按用户决定暂缓。远端分支保护是否强制检查与工作流是否执行是两项不同结论。
