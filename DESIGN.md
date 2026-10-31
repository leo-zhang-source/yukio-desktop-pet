---
name: Yukio Workbench
description: "A three-pane work monitor where every chat carries a live status and every statement says how it is known."
colors:
  ink: "#12151b"
  ink-hover: "#2a303b"
  live: "#0a66d0"
  live-on-rail: "#62aaf6"
  wait: "#8f4c00"
  wait-mark: "#e39a2d"
  wait-mark-on-rail: "#f0ab43"
  wait-soft: "#fdf2df"
  fail: "#b92d24"
  fail-on-rail: "#e0584e"
  fail-soft: "#fbe9e7"
  ink-2: "#3a4250"
  ink-3: "#5c6676"
  ink-disabled: "#7a8493"
  paper: "#ffffff"
  panel: "#f5f6f8"
  hover: "#eff1f4"
  press: "#e6e9ee"
  line: "#e2e5ea"
  line-2: "#cdd2da"
  rail: "#14171d"
  rail-2: "#1e222a"
  rail-3: "#2a2f3a"
  rail-line: "#272c36"
  rail-ink: "#f1f3f6"
  rail-ink-2: "#a3acba"
  state-quiet: "#8a93a2"
  state-ended: "#616b7a"
  state-unknown: "#6e7888"
typography:
  headline:
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "Segoe UI", "Microsoft YaHei", sans-serif'
    fontSize: "18px"
    fontWeight: 600
    lineHeight: 1.55
    letterSpacing: "-0.01em"
    fontFeature: '"tnum" 1'
  title:
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "Segoe UI", "Microsoft YaHei", sans-serif'
    fontSize: "15px"
    fontWeight: 600
    lineHeight: "24px"
    fontFeature: '"tnum" 1'
  title-sm:
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "Segoe UI", "Microsoft YaHei", sans-serif'
    fontSize: "14px"
    fontWeight: 600
    lineHeight: 1.5
    fontFeature: '"tnum" 1'
  body:
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "Segoe UI", "Microsoft YaHei", sans-serif'
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.65
    fontFeature: '"tnum" 1'
  body-sm:
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "Segoe UI", "Microsoft YaHei", sans-serif'
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.6
    fontFeature: '"tnum" 1'
  label:
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "Segoe UI", "Microsoft YaHei", sans-serif'
    fontSize: "13px"
    fontWeight: 500
    lineHeight: 1.4
    fontFeature: '"tnum" 1'
  label-strong:
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "Segoe UI", "Microsoft YaHei", sans-serif'
    fontSize: "13px"
    fontWeight: 600
    lineHeight: "23px"
    fontFeature: '"tnum" 1'
  caption:
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "Segoe UI", "Microsoft YaHei", sans-serif'
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.55
    fontFeature: '"tnum" 1'
  caption-strong:
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "Segoe UI", "Microsoft YaHei", sans-serif'
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.6
    fontFeature: '"tnum" 1'
  label-sm:
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "Segoe UI", "Microsoft YaHei", sans-serif'
    fontSize: "12px"
    fontWeight: 500
    lineHeight: 1.3
    fontFeature: '"tnum" 1'
rounded:
  sm: "4px"
  inner: "5px"
  md: "6px"
  track: "7px"
  lg: "8px"
  full: "50%"
spacing:
  2xs: "2px"
  xs: "4px"
  sm: "6px"
  md: "8px"
  row: "10px"
  lg: "12px"
  xl: "16px"
  gutter: "24px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "4px 12px"
    height: "30px"
  button-primary-hover:
    backgroundColor: "{colors.ink-hover}"
  button-secondary:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "4px 12px"
    height: "30px"
  button-secondary-hover:
    backgroundColor: "{colors.hover}"
  button-secondary-active:
    backgroundColor: "{colors.press}"
  button-disabled:
    backgroundColor: "{colors.hover}"
    textColor: "{colors.ink-disabled}"
  button-icon:
    textColor: "{colors.ink-3}"
    rounded: "{rounded.md}"
    size: "30px"
  button-icon-hover:
    backgroundColor: "{colors.hover}"
    textColor: "{colors.ink}"
  select:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "0 8px"
    height: "30px"
  search-field:
    backgroundColor: "{colors.rail-2}"
    textColor: "{colors.rail-ink}"
    rounded: "{rounded.md}"
    padding: "0 8px 0 10px"
    height: "32px"
  search-field-focus:
    backgroundColor: "{colors.rail-3}"
  rail-filter:
    textColor: "{colors.rail-ink-2}"
    typography: "{typography.label-sm}"
    rounded: "{rounded.inner}"
    padding: "0 6px"
    height: "26px"
  rail-filter-selected:
    backgroundColor: "{colors.rail-3}"
    textColor: "{colors.rail-ink}"
  tab:
    textColor: "{colors.ink-3}"
    typography: "{typography.label}"
    height: "34px"
  tab-selected:
    textColor: "{colors.ink}"
    typography: "{typography.label-strong}"
  chat-row:
    textColor: "{colors.rail-ink}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "7px 8px"
  chat-row-hover:
    backgroundColor: "{colors.rail-2}"
  chat-row-selected:
    backgroundColor: "{colors.rail-3}"
  certainty-mark:
    textColor: "{colors.ink-3}"
    typography: "{typography.label-sm}"
    rounded: "{rounded.sm}"
    padding: "0 6px 0 5px"
    height: "24px"
  tag:
    backgroundColor: "{colors.hover}"
    textColor: "{colors.ink-2}"
    typography: "{typography.label-sm}"
    rounded: "{rounded.sm}"
    padding: "0 6px"
  proof:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink-2}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.md}"
    padding: "9px 12px"
  panel:
    backgroundColor: "{colors.panel}"
    rounded: "{rounded.lg}"
    padding: "14px 16px"
---

# Design System: Yukio Workbench

## Overview

**Creative North Star: "The Honest Monitor"**

The workbench is a desktop tool a non-technical boss opens for seconds to learn how several AI assistants are doing. It should read like a well-kept status board: what needs you, one plain sentence about what is happening, and a mark that says how that sentence is known. Its strongest opinions are about what a colour or a shape is allowed to claim.

Density is desktop-tool tight: 14px reading text, 13px controls, 30px control height. A graphite rail, a white reading column and a pale slate inspector carry all the depth, so the page stays quiet enough for its few signals to stand out.

The user has rejected characters in this surface, and neither the earlier white-green interface nor the blue-white draft is a reference. The direction also refuses the long scrolling card stack and any skeuomorphic costume.

**Key Characteristics:**
- Three tone planes and one 1px line weight, with no decorative surfaces.
- Ink acts; blue, amber and red only report state.
- A finished turn stays neutral, and the palette has no success colour.
- Every statement carries a certainty mark that opens its evidence in place.
- System type from 12px to 18px, with tabular figures throughout.
- Motion only confirms: 100ms to 160ms state changes, plus one spinning ring for live work.

## Colors

A graphite-and-white tool palette with three status signals and no brand hue.

### Primary
- **Working Ink** (#12151b): Main text, the primary button, the selected tab and its underline, and light-pane focus rings. Hovers to **Ink Hover** (#2a303b).

### Secondary
- **Live Blue** (#0a66d0): Live work only: the working ring and the status of a chat with recent activity. **Rail Live Blue** (#62aaf6) is the same signal on graphite.
- **Waiting Amber** (#8f4c00): Text on amber surfaces and amber status words.
- **Amber Mark** (#e39a2d): The dot beside amber words. **Rail Amber Mark** (#f0ab43) is the same signal on graphite, for the waiting state mark and count.
- **Amber Wash** (#fdf2df): The background of attention blocks, notice bands and warning tags.
- **Failure Red** (#b92d24): Error text on Records. **Rail Failure Red** (#e0584e) marks a lost connection on graphite.
- **Red Wash** (#fbe9e7): The background of the error block.

### Neutral
- **Second Ink** (#3a4250): Secondary reading text, proofs and quiet status words.
- **Third Ink** (#5c6676): Labels, notes, times and unselected tabs.
- **Disabled Ink** (#7a8493): Disabled button text only.
- **Paper** (#ffffff): The reading column and secondary buttons.
- **Slate Panel** (#f5f6f8): The inspector and every tinted evidence block.
- **Hover Wash** (#eff1f4): Light-pane hover, tags, disabled fills and the segmented track.
- **Press Wash** (#e6e9ee): Light-pane pressed state.
- **Hairline** (#e2e5ea): Dividers between rows and panes.
- **Control Line** (#cdd2da): Borders of buttons and selects, and scrollbar thumbs.
- **Graphite Rail** (#14171d): The rail surface.
- **Rail Raised** (#1e222a): Rail hover, the search field and the filter track.
- **Rail Selected** (#2a2f3a): The selected chat, the selected filter and focused search.
- **Rail Line** (#272c36): The divider above the rail footer.
- **Rail Ink** (#f1f3f6): Primary rail text and rail focus rings.
- **Rail Ink Soft** (#a3acba): Rail meta lines, times, counts and placeholders.
- **Quiet Grey** (#8a93a2): The status dot when nothing is live or waiting.
- **Ended Grey** (#616b7a): The small dot of a finished chat.
- **Unknown Grey** (#6e7888): The dashed ring of a chat whose state is unconfirmed.

All readable text pairs clear 5:1. Amber Mark on Paper measures only 2.35:1, so it always sits beside words.

### Named Rules
**The Ink Acts Rule.** Working Ink is the only action colour: primary buttons, the selected tab, focus rings. There is no brand accent, and no status colour ever fills a button.

**The Three Signals Rule.** Blue is live work. Amber is a call on your attention: a chat waiting for you, or a caveat about the records. Red is failure. Each appears only with that meaning, and always with words, never as colour alone. The one other blue is the text-selection tint.

**The Neutral Finish Rule.** A finished turn is grey, never green, because finishing is not success.

Amber is also used where the person has to act on something, such as the banner asking them to reopen the workbench. Records marks failed, cancelled and uncertain operations with a neutral outlined tag, because that tone covers more than failure and red would overclaim.

## Typography

**Display Font:** None. The system has no display tier.
**Body Font:** The platform system stack: San Francisco, with PingFang SC for Chinese, then Segoe UI, Microsoft YaHei and sans-serif.
**Label/Mono Font:** System monospace, for record identifiers on Records only.

**Character:** Native and unnoticed. The panel sits beside Mac apps and mixes English with Chinese, and the system stack renders both well without loading anything.

### Hierarchy
- **Headline** (600, 18px, 1.55, -0.01em): The one lead sentence, and the empty-state heading.
- **Title** (600, 15px, 24px): The chat title in the header, on one line.
- **Title Small** (600, 14px, 1.5): Block headings and timeline event titles.
- **Body** (400, 14px, 1.65): Statements in spec rows and explanations.
- **Body Small** (400, 13px, 1.6): Proofs, quotes, fold contents and inspector text.
- **Label** (500, 13px, 1.4): Buttons, tabs and chat titles in the rail.
- **Label Strong** (600, 13px, 23px): Spec-row labels. The selected tab and status words share the size and weight.
- **Caption** (400, 12px, 1.55): Times, meta lines and notes.
- **Caption Strong** (600, 12px, 1.6): Section headings in the rail and inspector.
- **Label Small** (500, 12px, 1.3): Certainty marks, tags and small disclosures.

### Named Rules
**The Tight Scale Rule.** Reading and controls live at 12px, 13px and 14px. Only the chat title, the 17px metric values on Records and the headline go larger. Hierarchy comes from weight and ink step, not size.

**The Twelve Pixel Rule.** No text renders below 12px. Labels of 9px to 11px are a known failure for this reader.

**The Tabular Rule.** Figures are tabular everywhere, set once on the page body, so times and counts align without extra work.

## Layout

Three fixed panes fill the window: a 264px rail, a flexible reading column and a 284px inspector. The page never scrolls; each pane scrolls on its own, so search and the chat header stay in place.

Reading content is capped at 880px, or 900px on Records, inset 24px at the sides. Statements sit in spec rows: a 112px label column, a 16px gap and the value, with 12px above and below and a Hairline between rows. The label's 23px line matches the 14px body line, so both share a first baseline.

Spacing steps are 2, 4, 6, 8, 10, 12, 16 and 24px. Inside the Mac panel the rail adds 30px of top space to clear the window controls; the header and inspector take a fifth of that.

- **Above 1000px:** Three panes. While the inspector is open, the header hides its assistant and project line because the inspector already shows it.
- **1000px and below:** The inspector leaves the grid and becomes a 284px overlay drawer on the right.
- **700px and below:** The rail becomes a 280px off-canvas drawer over a dim scrim (#12151b66), side gutters narrow to 16px, and spec rows stack. The panel's 760px minimum means this path applies only in a narrower browser window.

## Elevation & Depth

The system is flat and tonal. Depth comes from three planes, graphite, white and pale slate, divided by hairlines. Nothing at rest casts a shadow. Inset rings on certainty marks draw the mark itself and are not elevation.

### Shadow Vocabulary
- **Segmented Thumb** (`box-shadow: 0 1px 2px #12151b26`): The selected option in a segmented control on a light pane.
- **Overlay Drawer** (`box-shadow: -8px 0 24px #12151b1f`): The inspector when it floats over content at narrow widths.

### Named Rules
**The Flat Rule.** Surfaces are flat at rest. A shadow appears only on a segmented thumb or a drawer that overlaps content.

## Shapes

Forms are small and gently rounded. Most things use one radius (6px): controls, rows, proofs and blocks. Tags, marks and the focus ring use 4px, the deep-explanation panel uses 8px, and only state dots are full circles.

Icons are authored inline SVG at 16px with a 1.4 stroke and round caps. Disclosure chevrons are drawn from two 1.5px strokes and turn 90 degrees when opened.

**The Nested Radius Rule.** Segmented tracks use 7px with 2px of padding, and their thumbs use 5px, so inner and outer corners stay concentric.

**The One Hairline Rule.** Every divider and control border is 1px. Outside the marks themselves, the only 2px lines are the selected-tab underline and the focus ring.

## Components

### Buttons
Quiet, dense desktop controls.
- **Shape:** Gently rounded (6px), 30px tall.
- **Primary:** Working Ink fill with white text. Used sparingly, for the action that sends the user's words to a model.
- **Secondary:** Paper fill with a 1px Control Line border. This is the default.
- **Hover / Focus:** Hover Wash with a slightly darker border (#bcc3cd), then Press Wash, over 120ms. Primary moves to Ink Hover, then black. Focus is the 2px ring at 1px offset.
- **Disabled:** Hover Wash with Disabled Ink text and a Hairline border.
- **Icon / Text:** Icon buttons are 30px square, Third Ink, and clear until hover. Text buttons use Second Ink with no border.

### Chips
- **Style:** Tags use Hover Wash, Second Ink and a 4px radius on a 19px line.
- **State:** Static labels, such as "Verification needed". Warning events on Records use Amber Wash and Waiting Amber.

### Cards / Containers
There are no cards. Reading content lies on hairlines, and tinted blocks hold what the reader opened.
- **Corner Style:** 6px, and 8px for the deep-explanation panel.
- **Background:** Slate Panel. A quote inside a tinted block flips to Paper, so nesting never stacks a third tone.
- **Shadow Strategy:** None.
- **Border:** None; tone alone separates the block.
- **Internal Padding:** 9px to 10px by 12px, and 14px by 16px for the panel.

### Inputs / Fields
- **Style:** Selects use Paper, a 1px Control Line and a 6px radius at 30px tall. On the rail they use Rail Raised with a Rail Selected border. Search is 32px of borderless Rail Raised with an icon and a `/` hint.
- **Focus:** Selects take the focus ring. Search fills to Rail Selected and hides the hint; it has no ring yet, which is a gap against the focus guardrail, not a pattern to copy.
- **Error / Disabled:** No field-level error state exists yet.

### Navigation
- **Rail filters:** A 7px Rail Raised track holds 26px options; the selected one fills Rail Selected. The waiting count turns amber and semibold when it is not zero.
- **View tabs:** Text tabs 22px apart and 34px tall, in Third Ink. The selected tab is Working Ink and semibold, with a 2px underline sitting on the header hairline. Keys 1 to 3 switch them.
- **Segmented control:** The same track on Hover Wash, with a Paper thumb.
- **Narrow widths:** The rail moves into its drawer, as described under Layout.

### Chat Row
Two lines in the rail: state mark, title and right-aligned time, then a meta line naming the assistant and project. Titles truncate to one line. Hover fills Rail Raised and selection fills Rail Selected, over 100ms.

### Certainty Mark
The signature component: one small form per statement, with a word beside it, which opens the evidence in place. The 9px form sits on a 24px target and hangs 5px left so it aligns with the text edge above. Hover adds Hover Wash.
- **Observed in records:** Solid ink disc.
- **Your requirements:** Solid ink square with soft corners.
- **Assistant's report:** Half-filled ring.
- **Interpretation:** Hollow ring in Third Ink.
- **Not yet clear:** Dashed ring in Third Ink.
- **Written by a model:** Small solid diamond.

A static variant, with no hover or evidence, labels recent activity.

### Chat State Mark
A 12px form on graphite, with a hidden text label for screen readers.
- **Working:** Open Rail Live Blue ring, spinning every 1.2s. Under reduced motion it closes and stops.
- **Waiting:** Rail Amber Mark disc with a drawn exclamation mark.
- **Ended:** Small Ended Grey dot.
- **Unknown:** Dashed Unknown Grey ring.

### Status and Notice Bands
- **Status:** A 9px dot and semibold words at the end of the header. Quiet by default, blue when live, amber when it needs you.
- **Attention block:** Amber Wash, a 6px radius and an Amber Mark dot, at the top of the reading column.
- **Notice band:** A full-width Amber Wash strip under the header, closed by a 1px warm line (#f3dfba).
- **Error block:** Red Wash with Failure Red text, on Records.

### Disclosure
Folds use a 36px summary row in Second Ink with a chevron, on a Hairline. Inspector folds shrink to 28px or 32px. Chevrons turn over 120ms.

**The Shape Carries It Rule.** Every chat state and certainty level has its own form, so each still reads in greyscale.

**The One Step Rule.** Evidence opens in place, directly below the statement it supports, and never sits more than one disclosure away from it.

## Do's and Don'ts

### Do:
- **Do** pair every status colour with plain words, and with a distinct form wherever it marks a chat or a statement.
- **Do** keep Working Ink for actions, and let everything else stay neutral.
- **Do** separate content with 1px Hairlines and tone, not boxes.
- **Do** open evidence in place from a certainty mark, on the Slate Panel tint.
- **Do** give every focusable element the 2px focus ring: Working Ink on light panes, Rail Ink on the rail, 1px offset.
- **Do** stop all transitions and the working ring's spin under reduced motion, leaving a closed ring.
- **Do** truncate names to one line in rails and headers, and let reading text break anywhere; real names run from 3 to 35 characters in two languages.
- **Do** draw icons as inline SVG at 16px with a 1.4 stroke and round caps.

### Don't:
- **Don't** show characters, the pet, or any art from the approved rig in the workbench. The user confirmed this: "不要人物".
- **Don't** colour a finished turn green, or add any success colour.
- **Don't** add a brand accent, or reuse a status colour for emphasis, links or buttons.
- **Don't** set text below 12px.
- **Don't** stack reading content in cards, or add shadows to resting surfaces.
- **Don't** add a second divider weight.
- **Don't** show a confirmed failure in amber.
- **Don't** use monospace outside record identifiers.
- **Don't** load fonts, images, scripts or styles from another origin, or write inline styles; the page security policy blocks them.
- **Don't** treat the earlier white-green interface or the blue-white draft as a reference.
