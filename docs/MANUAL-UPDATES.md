# Mac 更新 / Updating on Mac

[中文](#zh) · [English](#en)

<a id="zh"></a>
## 中文

**5.4 Preview 1（55）是预览版。** 旧版使用者需从[发布页](https://github.com/leo-zhang-source/yukio-desktop-pet/releases/tag/v5.4-preview.1)手动安装一次；旧更新地址无法自动迁移。5.3 稳定下载继续保留。

1. 退出雪绪，保留旧 App 和自己的数据备份。
2. 打开 DMG，把新 `Yukio.app` 替换到原安装位置；不要删除聊天和配置。
3. 重新打开，确认版本为 5.4（55），检查原有聊天与设置。临时签名改变后可能需要重新授予准确 App 辅助功能权限。

本包使用新仓库的独立、签名预览更新源；稳定版不会因此自动安装预览版。检查与安装仍由 App 显示提示。包尚未 Apple 公证，完整首次使用与升级验收范围见[发布记录](releases/5.4-preview.1.md)。

回退时先退出，再恢复旧 App；保留新数据，不能用旧数据库覆盖新增记录。数据通常在 `~/Library/Application Support/YukioPlayer/activity-observation/`，不在 App 内。卸载前关闭登录启动，再退出并移除 App；助手中的 hooks 需按原连接说明单独处理。

<a id="en"></a>
## English

**5.4 Preview 1 (55) is a preview.** Users of older versions must manually install it once from the [release page](https://github.com/leo-zhang-source/yukio-desktop-pet/releases/tag/v5.4-preview.1); old update URLs cannot migrate themselves. The stable 5.3 download remains available.

1. Quit Yukio and keep backups of the old App and your data.
2. Open the DMG and replace `Yukio.app` in its existing location. Do not delete chats or configuration.
3. Reopen, confirm version 5.4 (55), and check existing chats and settings. A changed ad-hoc signature may require granting Accessibility to the exact App again.

This package uses a separate signed preview feed in the new repository. Stable users will not be automatically enrolled. The App still prompts before installation. The package is not Apple-notarized; see [release evidence and limits](releases/5.4-preview.1.md).

For rollback, quit first and restore the old App, preserving new data rather than replacing it with an older database. Workbench data normally lives at `~/Library/Application Support/YukioPlayer/activity-observation/`, outside the App. Before uninstalling, turn off Launch at login, quit and remove the App. Assistant hooks need separate cleanup under the connection instructions.
