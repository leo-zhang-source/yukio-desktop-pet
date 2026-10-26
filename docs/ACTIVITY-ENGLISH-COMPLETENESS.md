# Complete English presentation

Mac 0.4.11 embeds workbench 0.3.8. The earlier 0.4.10 automatic-installer investigation remains separate and deferred. This change does not retry or repair automatic installation.

## Implemented

- Translate composed operation/results messages, task recap limits, handoff states, error messages and generated fallback chat names, rather than only matching complete static headings. Unknown source text is never partly translated into a misleading mixture.
- Preserve actual chat names, project names and original quotations, as explicitly requested. Local project background in another language stays in the original-text disclosure; the home context labels the current quoted request as original text.
- Require generated model prose and history headings to be English in English mode. Reject mixed Chinese/English responses and keep the English fallback instead of displaying an unchecked answer. Source evidence retains its language.
- An explicit language selected in Yukio also controls the workbench, including its native header and embedded settings. Without an explicit app preference, the workbench follows the system language. Switching the setting refreshes the page language while retaining the selected chat. This changes labels and status text without rewriting that preference. Standalone launch messages and App display-name resources also have English text.

## Verification

Backend, page and native regression checks are recorded with the local delivery artifacts. A bounded excerpt from the current real chat produced three English paragraphs through the existing configured LAN model. The test server permitted at most one model call and was stopped after closing the page. This confirms that case, not every possible explanation.

## Unverified and issues

ZIP, DMG and the separate desktop English copy match all 470 App files. The original App, history and private configuration are retained. The native English header and controls were observed; final full-page review is blocked by system Screen Time. No system restriction was changed. See [delivery verification](validation/mac-english-0.4.11/README.md). Windows, other Macs, multi-day use and Apple notarization remain unverified or deferred. Automatic installation is still unaccepted.
