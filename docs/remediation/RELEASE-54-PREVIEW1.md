# Mac 5.4 Preview 1 · build 55

## Source and package / 源码与安装包

Product source / 产品源码：`cb507e73c1745e1cca84a8b6dc1e9710109f2109`，tag `v5.4-preview.1`，workbench `0.4.7`。

本包沿用 host 41.6 产品线。原生界面源码、前端与角色素材保留；增加离线指南、包版本和独立签名预览更新源。整改候选 54 的不同界面与完整修复集另存于 `codex/remediation-baseline`，不能视为全部合入此包。标签与包内 `BUILD-PROVENANCE.json` 指向同一产品提交；主线后续仅补充发布记录与已签名更新列表。

This package follows the host 41.6 product line, preserving its native UI source, frontend and character assets. Candidate 54 remains on the separate remediation branch. The package and release tag identify the same product commit; later main commits add delivery records and the signed update feed only.

| File | SHA-256 |
| --- | --- |
| `Yukio-5.4-preview.1-macOS-arm64.zip` | `f6804fb9bb4cba094eaf93696e6f53e41b826c1dd7afaa655133c0156dbd0059` |
| `Yukio-5.4-preview.1-macOS-arm64.dmg` | `fa66158b657014691ac97d71becdc583fba05566eb67c582f62e7621c36c79d7` |

## Verified / 已验证

- 两轮完整本机回归一致：每轮 Swift 247、Python 334、Node 51、共享检查 230，零跳过、零意外失败；两项负向对照均捕获预期错误。另有 14 项打包／更新源检查通过。
- 实际 DMG 在独立 Tart Mac VM（macOS 26.6.2 / 25G83，arm64）安装；491 个包内文件及离线指南哈希与构建记录一致，严格签名检查、原生 `--check`、内置运行环境 `--check` 通过。
- VM 中启动实际 App，使用测试用户自己的登录对合成 QA 聊天调用 Codex 与 Claude：分别约 12.9 秒、5.39 秒，均返回 `mode=model`；历史接口可读，测试后恢复解释设置与原 VM App。
- ZIP 与更新列表使用现有 Keychain 密钥签名并验证；密钥不导出。预览更新列表位于 `updates/preview.xml`，不覆盖稳定版更新通道。
- 上传差异扫描未发现密钥或数据库／安装包误入源码。离线指南结构、双语锚点及无外部渲染依赖已检查。

Two consistent local regression runs and the actual DMG installation were checked. Real assistant calls used the VM test user's own accounts and synthetic QA content. The VM has its own disk, application data and credentials, while sharing host hardware and network. It already contained QA data; this is not a clean first-run acceptance test.

## Remaining limits / 未完成范围

App 为临时签名、未公证。本次未完成干净系统的公开下载首次使用全流程、Gatekeeper、公证、最低 macOS、Intel、所有客户端组合及真实自动升级全过程验收。离线 HTML 未进行浏览器目视验收。不能把以上局部结果当作通用化全部完成。Windows 与云端 Cowork 按用户决定暂缓。

The App is ad-hoc signed and not notarized. Clean first-run acceptance, Gatekeeper, minimum macOS, Intel, all client combinations and an end-to-end automatic upgrade remain unverified. The offline HTML received structural, not browser visual, checks. Windows and cloud Cowork are deferred.

## Publication and installed copy / 发布与实际运行版本

[GitHub Release](https://github.com/leo-zhang-source/yukio-desktop-pet/releases/tag/v5.4-preview.1) 已公开，标记为预览版。匿名回读 DMG、ZIP、校验文件、预览源与 HTML；包哈希与上表一致。公开更新列表与 Release 附件逐字节一致，列表及 ZIP 签名验证通过。稳定版 `v5.3` 仍为 GitHub latest。

桌面入口指向的实际 App 已替换为公开下载 ZIP 中的 5.4（55），启动后健康接口正常。491 个文件与构建记录一致，291 个界面／角色资源文件与原 41.6 相同；原有 149,324 条 Codex、12,917 条 Claude 历史记录逐条哈希核对保留，配置及全局 Codex 配置未变，原有辅助功能读取权限可用。旧 App 和数据备份保留在本机私有备份目录。

Public assets were downloaded without authentication and matched the build hashes and signatures. The actual desktop App now runs build 55 from that downloaded ZIP, with all 491 files matching the build manifest. Existing history and settings were preserved; the previous App and private data backups remain local. Stable v5.3 remains the default latest release.

发布后主线只增加更新列表、CHANGELOG 与本记录；产品源码、下载包、标签和实际安装版本均指向上面的产品提交。整改候选源码已同步至独立分支，未将其不同界面覆盖到桌面。

源码快照、DMG、ZIP、签名更新源与构建记录已归档至私有 NAS；归档文件 SHA-256 全部通过，ZIP 另行完整回读核对。公开 README 与中英文入口共 8 个文件已回读一致，当前主要文档 91 个本地链接有效。私有凭据与聊天数据库不随发布上传。

Source, packages and build records were archived to private NAS storage with checksum and ZIP readback verification. Eight public bilingual entry documents match the prepared copies; 91 local documentation links resolve. Private credentials and chat databases are excluded from publication.
