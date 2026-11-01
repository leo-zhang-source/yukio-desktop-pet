# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

The workbench is a local web page hosted in a native Mac panel (WKWebView inside `WorkbenchPanel.swift`). Its pages follow web conventions; the panel around it follows Mac conventions.

## Users

An ordinary Mac user who runs several AI assistants at once (Codex, Claude Code, Deep Code) and does not read code. The primary user calls themselves the boss: they hand work to AI, then want to know how it is going without becoming an engineer. Yukio is distributed to other people, so nothing may assume the author's machine, accounts or services.

They open the workbench from the desktop pet in the middle of something else, usually for seconds at a time, and sometimes stay to read.

## Product Purpose

Let a non-technical person supervise AI work in plain language. In order of frequency, confirmed by the user on 2026-10-31:

1. See current progress: which chats are working, which one is waiting for me, what just finished.
2. Understand a piece of work: its goal, its method, and whether it is actually working.
3. Pick up earlier work: after a break, what happened before and what comes next.

Checking raw evidence stays fully available but is a secondary, on-demand task.

Success means the user can glance, know the state of their work, and return to what they were doing.

## Positioning

A character who sits on your desktop and follows your AI assistants, and a workbench that tells you in plain language what they are doing. It reads local records and separates what was observed from what an assistant claimed and from what is inferred. Tool success is never presented as task success.

## Operating Context

- Opened by right-clicking the desktop pet. Hosted in a floating panel that stays above other windows and closes when the user clicks outside it. The user confirmed on 2026-10-31 that this behaviour stays. Default 1100×760 points, minimum 760×520.
- Everything runs on the user's own Mac. The page polls a loopback service; reading records never calls a model.
- The same window also holds the native pet settings. Preferences stay native and never pass through the page.
- Interface language is English by default and switchable to Chinese. Chat and project names stay in their original language.

## Capabilities and Constraints

- Sources: Codex, Claude Code, Deep Code. Real data on the author's Mac: 34 chats shown (capped at 60), 24 with no project, names from 3 to 35 characters, several distinct projects sharing one name.
- Chats and projects are matched by identity, never by title. Two projects with the same name stay separate.
- Explanations are optional and off until the user turns them on. They use the user's own Codex or Claude Code account quota, or a self-hosted LAN model. Only short excerpts of the selected chat are sent. Provider, consent, grant and hourly limits are enforced by the existing logic and must not be weakened.
- No model call happens without the page being open. Closing the panel revokes its grant.
- Page security policy allows only same-origin scripts, styles and images. No external resources, no inline scripts or styles.
- Windows is deferred; shared code is maintained for Mac.
- Terms that must stay honest: 记录所见 (observed), 助手自述 (assistant's own claim), 你的要求 (your request), 推测 (inference), 尚不清楚 (unknown).

## Brand Commitments

- Name: Yukio / 雪绪. Second skin: 千夏.
- Approved character art under `sources/approved-animation-rig/` must not be altered or regenerated for interface decoration.
- Palette: white and green, chosen by the user on 2026-10-31 after trying a dark console. Regions must read apart at a glance without turning into a rainbow.
- The workbench shows no characters. Confirmed by the user on 2026-10-31 after seeing a character-led sketch: "不要人物". It must look professional and put functionality first. The pet stays on the desktop; the workbench is a work tool.

## Evidence on Hand

- Live local records through the workbench service; synthetic mode for labelled demonstrations.
- Issue list with confirmed copy and first-run problems: `docs/remediation/ISSUES-TO-FIX.md` (YK-01, YK-06, YK-12 touch this surface).
- No testimonials, usage numbers or customer claims exist. None may be invented.

## Product Principles

1. Answer "how is it going?" before anything else. Status and the thing waiting for you come first.
2. Plain language first, evidence one step away. Never make the user open three layers to reach a fact, and never hide that a fact is uncertain.
3. Never overclaim. Observed, claimed and inferred stay visibly different; unknown stays unknown.
4. Spending the user's quota or sending their words elsewhere is always visible and always their choice.
5. Glanceable. The panel is opened for seconds and closes on an outside click, so the state of work must read instantly.

## Accessibility & Inclusion

Full keyboard use, visible focus, reduced-motion support, and status conveyed by more than colour. Text must stay comfortably readable for a non-technical reader; the current 9–11px labels are a known failure.
