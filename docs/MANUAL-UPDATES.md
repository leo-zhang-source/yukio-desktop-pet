# Updating Yukio on Mac / Mac 雪绪更新方式

## 当前状态（2026-10-31）

旧 GitHub 账号已不可用。历史安装包和已安装 App 仍包含旧更新地址，因此软件内更新目前不可用；恢复历史 `appcast.xml` 不代表更新服务恢复。**请使用新账号的 [Mac 5.3 下载页](https://github.com/leo-zhang-source/yukio-desktop-pet/releases/tag/v5.3)**。这是原公开包，不是迁移后重新构建的新版；5.4 仍为未完成独立环境验收的候选。

1. 先核对当前版本。已使用高于 5.3 的测试版本时，不要为了换账号而降级。
2. 下载 DMG 或 ZIP，并按发行页的 SHA256SUMS 核对文件。
3. 退出 Yukio，在原安装位置替换 `Yukio.app`，再打开。建议保留一份位于“应用程序”的实际 App；桌面可使用替身。
4. 聊天、模型配置与设置保存在 App 外，不需要复制进安装包。保留原 App 备份以便恢复。
5. 包目前采用临时签名，未完成 Apple 公证。首次打开受阻时，核对来源后按 macOS 的“系统设置 → 隐私与安全性”正常提示处理；无需关闭系统保护。

下一次正式更新需同时完成新账号更新源、签名、公开下载和独立用户安装验证。当前迁移没有替换作者正在使用的 5.3.2 (38)，也没有将 5.4 候选标为可发布。Windows 下载继续暂停。

## Current status

The old account and embedded update endpoint are unavailable. In-app updates currently cannot complete. Use the [new-account Mac 5.3 release](https://github.com/leo-zhang-source/yukio-desktop-pet/releases/tag/v5.3) for manual installation. Verify its checksum, quit Yukio, replace the App in its existing location and reopen it. Do not downgrade a newer test build solely to change accounts. Settings and history remain outside the App.

The restored files are original historical packages, ad-hoc signed and not notarized. The 5.4 candidate still requires independent acceptance. A future release must validate the new signed feed and real installation flow together. Historical update tests describe their original environments; they do not establish that the suspended account's update service still works.

[Migration status](GITHUB-MIGRATION.md) · [Historical update verification](validation/mac-update-1.0/README.md) · [Mac candidate acceptance](remediation/STAGE4-DELIVERY.md)
