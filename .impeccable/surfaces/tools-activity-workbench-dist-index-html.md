---
version: 1
slug: "tools-activity-workbench-dist-index-html"
primary_target: "tools/activity-workbench/dist/index.html"
related_targets: ["tools/activity-workbench/dist/history.html"]
---

# Workbench surface brief

Scope: every workbench page (current work, records) and the native shell around them. Mode: Operate.
Audience and job: a non-technical boss supervising several AI assistants, opening a floating panel for seconds to learn how work is going, sometimes staying to read. Actions: see status, understand a chat, pick up earlier work. Evidence is on demand.
Constraints: panel stays floating and closes on outside click. No characters. Same-origin assets only. Existing consent, grant and epoch logic stays intact.

## Direction contract

THESIS: A three-pane work monitor where every chat carries a live status and every statement carries how it is known. Refuses the long scrolling card stack, repeated titles, nested disclosure, and any character or skeuomorphic costume.

OWN-WORLD: Ink graphite rail, white reading column, pale slate inspector, one hairline weight. Ink is the action colour. Blue means live work only, amber means waiting for you only, red means failed only; a finished turn is neutral because finishing is not success. System type at a tight scale, tabular times.

STORY: The visitor sees what needs them, reads one plain sentence about what is happening, knows how certain that sentence is, and leaves. Staying, they switch to understanding or earlier work without losing the chat.

FIRST VIEWPORT: Left rail with search, status filters and counts, compact chat rows. Centre header with title, status, and Now / Understand / Earlier tabs, then the lead sentence and spec rows, all above the fold at 1100×700. Right inspector with assistant, project, last activity, the request, and explanation controls.

FORM: Standard desktop three-pane tool, the category standard executed at full craft, chosen by the user over character-led directions. Signature move: certainty marks, one small glyph per statement for observed, claimed, inferred or unknown, which open evidence in place. seed:b586e62e19398708

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
