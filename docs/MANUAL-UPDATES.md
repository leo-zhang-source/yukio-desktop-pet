# Updating Yukio on Mac / Mac 雪绪更新方式

Yukio 0.4.13 checks for new releases and reminds you. It does not download or install an update inside the app.

1. Keep **Settings → More → Automatically check for updates** enabled for reminders. Turn it off to opt out. **Check for updates** works on demand.
2. When a new version is found, choose **Open download page**. **Later** leaves the current app running; a later scheduled check may remind you again.
3. On the official GitHub release page, download the complete Mac DMG or ZIP for Apple silicon.
4. Quit Yukio. Replace your existing App in the **same location**, keeping one installed copy. If yours is on the Desktop, replace that copy rather than also adding another in Applications. If the current copy is named **Yukio English**, give the downloaded App that same name before replacing it; do not keep both.
5. Reopen Yukio and check the version in Settings. Chats and private model configuration remain in Application Support, outside the App bundle.

The normal check schedule is six hours; a due startup check is attempted after about 15 seconds. No newer release means no background reminder. A network error does not exit or replace the current app. This release keeps signed-feed and signed-archive verification and the operating system's normal protections. The build remains ad-hoc signed and not notarized.

中文：雪绪自动检查新版并提醒你。点“打开下载页”，下载完整 Mac 版；退出雪绪后，在原位置替换现有程序，再重新打开。点“稍后再说”会保留当前程序；关闭“自动检查新版本”可停止后台检查。**不会自行下载、安装或重启**，也不会再进入原来的“正在安装”流程。桌面已有一份时就替换那一份，避免在其他位置再装一份。如果原名称是 **Yukio English**，先把下载的新程序改成同名再替换，不要两份都保留。聊天记录和设置单独保存在本机。

This is the Mac update flow. Windows still uses its earlier release and remains an optional follow-up.

Design references: [Sparkle informational updates](https://sparkle-project.org/documentation/publishing/#downloading-from-a-web-site), [automatic-check and automatic-install settings](https://sparkle-project.org/documentation/customization/), [user-driver choices](https://sparkle-project.org/documentation/api-reference/Protocols/SPUUserDriver.html).
