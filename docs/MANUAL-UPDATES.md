# Updating Yukio on Mac / Mac 雪绪更新方式

## Yukio 5.3 and later

1. Keep **Settings → More → Automatically check for updates** enabled for reminders, or use **Check for updates** whenever you want.
2. When a newer version is found, choose **Install Update**. Yukio downloads and verifies the package, installs it in the same location and reopens. **Remind Me Later** keeps your current App. Checking alone does not install anything.
3. If macOS asks to access the folder containing your installed App, respond in the system prompt. Do not disable system protections or grant full disk access. Installing in Applications avoids asking the updater to access your Desktop folder. A pending system prompt can leave the update waiting.
4. Chats, model configuration and settings are kept separately from the App. Keep one installed copy named **Yukio**.

The current public app version is **5.3**. Subsequent releases use **5.4 → 5.5**, then **6.0** for a major release. The earlier 1.0 label was a numbering mistake, not a version-count reset. The internal build number increases separately so existing clients recognize the newer release. Historical version names stay unchanged.

## Users currently on 0.4.11 or 0.4.12

The installable update feed restores **Install Update**. A real 0.4.11 executable successfully downloaded, installed and reopened 1.0 in isolated testing, with language, scale and a preference marker preserved. This was tested on this Mac in the user's Applications directory; it is not a claim that every Mac or installation location has been tested.

## Users currently on 0.4.13

0.4.13 was compiled with a download-page-only driver. A new update feed cannot change that code. Install the complete 5.3 DMG or ZIP **once**: quit Yukio, replace the existing App in the same location and reopen. If it is on your Desktop, replace that copy instead of adding another elsewhere. Future versions can then update inside Yukio normally. No private settings need to be copied into the App.

## 中文

1. 在“设置 → 更多”保留自动检查，或主动点“检查更新”。
2. 发现新版后点“安装更新”，雪绪会下载、检查、安装并重新打开。点“稍后提醒”会保留当前程序；只检查不会安装。
3. 如果 macOS 询问访问程序所在文件夹，请在系统提示里确认。无需关闭安全保护或开启完全磁盘访问。装在“应用程序”中，可以避免更新时请求读取“桌面”。
4. **目前用0.4.13的用户，需要先下载并替换完整5.3版本一次**，之后才能恢复软件内更新。其他旧版已用真实0.4.11验证升级。始终只留一份 **Yukio**；聊天、设置和模型配置另存于本机。

The check schedule remains six hours, with a due startup check after about 15 seconds. Opting out stops background checks. Network and signature failures leave the old App intact. Signed-feed and archive verification remain required. This Mac release is ad-hoc signed, not notarized. Windows remains optional on its unchanged 0.4.6 release.

[Verification](validation/mac-update-1.0/README.md) · [Sparkle update configuration](https://sparkle-project.org/documentation/customization/) · [Publishing installable updates](https://sparkle-project.org/documentation/publishing/)

Users already on the interim **1.0** can update normally inside the app to **5.3**. It is retained as a historical release; it is not the current version.

目前使用临时编号1.0的用户，可以直接在软件里更新到5.3；无需自己再替换一次。当前正式编号为5.3，后续继续5.4、5.5。
