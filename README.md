<div align="center">

# Yukio

### See your AI at work.

A Mac desktop companion that animates coding activity, explains progress and alerts you when your input is needed.

<img src="docs/readme/desk.gif" width="192" alt="Yukio reads, writes, checks her work and raises a completion sign">

**English** · [简体中文](README.zh-CN.md)

**[Download Mac preview](https://github.com/leo-zhang-source/yukio-desktop-pet/releases/tag/v5.4-preview.1)** · [Quick start](docs/MAC-USER-GUIDE.md) · [Online animation demo](https://is.gd/yukioapp)

</div>

## Why Yukio

When AI agents work on several tasks, users often switch between chats just to learn what is happening or whether an agent needs them. Yukio brings that information onto the desktop, making progress and requests for attention easier to notice.

## Highlights

- **Visible activity:** twelve animations for reading, coding, testing, waiting for input and more, with two characters—Yukio and Qianxia.
- **Readable progress:** a workbench shows current work, its purpose and history, with optional AI explanations and supporting excerpts.
- **Multi-chat notices:** see activity across chats, choose which one to follow, and catch questions and completed turns.
- **Nearby responses:** connect a supported assistant to answer questions and review approval requests beside the companion.

Follows local **Codex, Claude Code and Deep Code** activity. AI explanations use your own Codex or Claude Code account.

<img src="docs/readme/workbench-current.png" width="900" alt="Activity workbench with chat navigation, current work and explanations">

<sub>Illustration using an earlier interface and demo data. Layout depends on the installed version.</sub>

## Try it

1. **Install:** open the DMG, drag `Yukio.app` to Applications and launch it.
2. **Explore the animations:** right-click the companion, open Yukio settings and choose Play demo. Try dragging, resizing or switching characters.
3. **Follow real work:** stop the demo, enable Follow activity, start a small task in your local coding assistant, then select that chat in the workbench.

To try explanations or answer delivery, connect your own assistant using the [quick start](docs/MAC-USER-GUIDE.md).

## Downloads and scope

For **Apple silicon Macs, macOS 13+**, with English and Chinese interfaces. **5.4 Preview 1 (55)** preserves the current desktop workbench layout and updates Agent explanations, Codex client discovery and bilingual help. This is a preview under testing. Windows and cloud Cowork are deferred.

The package is not notarized; see [first-launch instructions](docs/MAC-HELP.md#install). Older versions need one manual installation; see the [current update instructions](docs/MANUAL-UPDATES.md#en).

Activity records and search stay local. Enabling AI explanations sends relevant chat excerpts and uses the selected account's allowance.

## Technology and resources

A native **Swift / AppKit** companion with a **Python / JavaScript** activity workbench. Animations use transparent layers, localized motion and independent blinking.

[What changed](docs/releases/5.4-preview.1.md) · [Usage and troubleshooting](docs/MAC-HELP.md) · [Documentation](docs/README.md) · [Source and build](docs/remediation/MAC-BUILD.md) · [Development and validation](DEVELOPMENT.md) · [Report an issue](https://github.com/leo-zhang-source/yukio-desktop-pet/issues)
