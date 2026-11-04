# Mac 5.4 Preview 2 · build 56

产品提交：`bc95722ef6c31f2bf2ab82e4c2bee6759e9508a0`；标签 `v5.4-preview.2`；工作台 `0.4.8`。

本次将首次使用修复按用户明确要求整理为预览发布。功能源码与本地候选 `9867c6e9` 一致，仅更新发布元数据与双语说明；从新提交重新构建 DMG、ZIP 和包内指南。保留现用工作台布局与全部 269 项角色资源。

| 文件 | SHA-256 |
| --- | --- |
| `Yukio-5.4-preview.2-macOS-arm64.dmg` | `30a1f994210fb42423e74d60fda9b1a90ccccd4ae140259a883fa96a8a6e2ec9` |
| `Yukio-5.4-preview.2-macOS-arm64.zip` | `173d6b41130216fa92abec270efb52612a5369d563a2d4a297c4a931dc705fb1` |

## 检查范围

- 修复代码回归：Swift 248 串行、Python 334、网页 52 通过；首次 Swift 并行运行有一项计时失败，保留在[首次使用记录](FIRST-RUN-20261104.md)。发布整理另有 9 项构建／更新源检查通过。
- 同提交完整构建、严格签名、包内资源和隔离数据目录下的内置运行环境检查通过；ZIP 内外指南与仓库 HTML 一致。
- ZIP 与预览更新列表使用现有 Keychain 密钥签名并验证，不导出私钥。稳定更新源不变。
- 上传差异未发现凭据或数据库误入源码；101 个文档内文件链接有效。

## 尚未完成

**完整首次使用验收仍未通过，按用户要求暂停。** 原 Preview 1 的公开下载、安装、系统放行与部分基础操作有实际证据；不能将其直接当作本包全部通过。修复包独立环境界面复验、测试用户登录后的真实任务与多聊天流程仍待验。App 临时签名、未 Apple 公证；最低 macOS、Intel 和完整自动升级未验证。Windows 与云端 Cowork 按用户决定暂缓。

## 上传与实际运行核对

[Preview 2 Release](https://github.com/leo-zhang-source/yukio-desktop-pet/releases/tag/v5.4-preview.2) 已公开为预览版，包含 DMG、ZIP、校验文件、签名预览源与离线指南。匿名下载全部附件，包哈希与上表一致；预览源与主线逐字节一致，更新列表和 ZIP 签名验证通过。稳定版 `v5.3` 仍为 GitHub latest。

桌面实际 App 已从公开下载的 ZIP 更新至 5.4（56），运行进程路径及健康接口正常；全部 491 项文件与构建清单一致。269 项角色资源不变，已有聊天记录逐条哈希核对保留，配置未变。旧 App 与数据备份保留在本机私有备份目录。

源码快照、安装包、更新源、构建清单已归档到私有 NAS 并逐文件校验。私人凭据、聊天数据库及本机备份不随 GitHub 发布。上述发布与本机运行检查不替代暂停的独立环境验收。

## English

Product commit: `bc95722ef6c31f2bf2ab82e4c2bee6759e9508a0`; tag `v5.4-preview.2`; build 56; workbench 0.4.8. The feature code matches the tested local candidate; release metadata and bilingual documentation were updated before rebuilding both archives. All 269 character assets are unchanged.

Local checks passed: 248 serial Swift, 334 Python and 52 web checks, plus nine packaging/update checks. The initial parallel Swift timing failure remains recorded. Package signatures, resource checks, isolated-data runtime checks and offline-guide consistency passed. The preview feed and ZIP were signed without exporting the Keychain key; the stable feed is unchanged.

**Full first-run acceptance remains incomplete and paused.** Revised-package GUI verification, signed-in real tasks and concurrent chats remain pending. The App is ad-hoc signed and not notarized. Windows and cloud Cowork remain deferred.

Preview 2 is public as a prerelease. All five assets were downloaded without authentication; archive hashes, update signatures and bundled guides match the prepared files. Stable v5.3 remains GitHub latest. The desktop App now runs build 56 from that public ZIP, with all 491 manifest entries matching and existing history/settings preserved. Previous App/data backups remain local. The source and release artifacts were archived to private NAS and checksum-verified. These checks do not complete independent first-run acceptance.
