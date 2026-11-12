# Mac setup and troubleshooting

[Back to quick start](MAC-USER-GUIDE.md) · [简体中文](MAC-HELP.zh-CN.md)

<a id="version"></a>
For Apple silicon Macs running macOS 13+. These steps cover 5.4 Preview 3 (63); older versions may use different controls.

<a id="install"></a>
## 1. Install

1. Get the Mac DMG from the [download page](https://github.com/leo-zhang-source/yukio-desktop-pet/releases/tag/v5.4-preview.3).
2. Open it, drag **Yukio.app** to Applications, then launch it from there.
3. If macOS cannot verify the developer, and you trust the download, use System Settings → Privacy & Security → Open Anyway. The current package is not notarized.

An avatar appears in the menu bar. The companion hides while idle by default; choose Show Yukio or Play demo in Settings.

<a id="first-run"></a>
<a id="follow"></a>
## 2. Get started

1. Choose **menu-bar avatar → Activity workbench**, or right-click the visible companion.
2. Choose Settings at the upper right of the workbench to set language, skin and size.
3. Enable Follow activity. Set Assistant to Auto and Pet follows chat to Automatic.
4. Start a task in Codex, Claude Code or Deep Code under the same Mac user. Yukio changes animations when she reads the local activity.

Try Play demo to preview animations, then Stop demo. Ordinary browser chats may not provide supported local activity.

<a id="explain"></a>
## 3. Enable explanations (optional)

You can view activity without this. Set it up when you want explanations of the work.

1. Follow the official [Codex](https://learn.chatgpt.com/docs/codex/cli) or [Claude Code](https://code.claude.com/docs/en/setup) instructions to install and sign in on this Mac. A website login alone does not sign in the local client.
2. At the top of the workbench, select that assistant under Explain with. The choice saves immediately without enabling disabled explanations.
3. Choose Enable explanations and select a chat. Follow the page's readiness message if installation, sign-in or a client update is needed.

<a id="privacy"></a>
Explanations send short chat excerpts to your selected assistant and use **your own account allowance**. Choose Stop automatic explanations to stop; closing the workbench stops further sends. Ordinary users do not need Qwen setup.

<a id="workbench"></a>
<a id="daily"></a>
## 4. Everyday use

| To… | Do this |
| --- | --- |
| See current work | Select a sidebar chat and read Happening now |
| See detail or history | Choose Explain the current activity in detail, or open Work history; without explanations it shows local records; with explanations enabled, expanding history groups may generate summaries on demand |
| Change the companion's chat | Expand the speech bubble and choose a chat card; restore Automatic in Yukio settings to resume automatic following |
| Move or resize her | Drag the companion; adjust Size in Yukio settings |
| Clear a completion sign | Yukio settings → Lower sign |
| Start at login | Enable Launch at login and complete any system approval |
| Quit | Menu-bar avatar → Quit Yukio |

<a id="answers"></a>
## 5. Answer questions (optional)

Enable Answer here in Yukio settings. This is separate from enabling explanations.

- **Claude Code:** menu-bar avatar → Connect Claude background answers, then restart Claude Code.
- **Codex:** the chat needs an existing background connection. If sending is unavailable, answer in the original chat.
- **Deep Code:** requires an extra adapter; follow Background answer setup in the menu bar.

Check the chat name, then select an answer or type a reply. Read the full approval request before allowing or denying it. If delivery may have happened without confirmation, check the original chat before retrying.

<a id="troubleshooting"></a>
## 6. Common problems

| Problem | Try this |
| --- | --- |
| Companion missing | Open the workbench from the menu bar → Yukio settings → Show Yukio / Reset position; check Hide when idle |
| No activity | Stop demo, enable following, check that your local assistant is working and that another chat is not pinned |
| New button missing | In this preview, Explain with is at the top of the workbench; pet Settings is at the upper right |
| Explanations fail | Check sign-in and service access in the assistant itself, then allowance and network |
| Workbench disconnected | Choose Reconnect; if needed, quit and reopen Yukio |
| Completion sign stays up | Use Lower sign manually; for automatic chat recognition, follow settings to grant Accessibility to the actual App |

<a id="updates"></a>
## 7. Update

Older versions require one manual installation of this preview: **quit Yukio → keep a backup of the old App → replace Yukio.app in Applications → reopen**. Keep your chats and settings; do not delete the user data folder. [Update and rollback details](MANUAL-UPDATES.md#en)

<a id="verification"></a>
*The new version is still being tested; complete first-run acceptance remains unfinished. [Current progress](../DEVELOPMENT.md)*
