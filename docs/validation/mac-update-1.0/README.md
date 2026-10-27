# Yukio 1.0 candidate — existing-user update verification

**Status: not published. Final installation has not passed.** The public release and installed desktop App remain 0.4.13. Windows is optional and its 0.4.6 files are unchanged.

**Implemented:** Restore Sparkle's localized, maintained install UI. A new installable feed item must not be marked informational. In 1.0, the user's Install Update choice authorizes that one download/install/relaunch cycle; a background check or a previous staged update does not authorize silent installation. Signed-feed verification, verification before extraction, automatic-check opt-out and the six-hour schedule remain. Both update-note languages use short Markdown, rendered as normal text instead of raw Markdown inside a preformatted box.

**Version policy:** Public app releases use `1.0`, `1.1`, `1.2`, etc.; significant major releases use `2.0`. There is no public third patch component for future releases. The separate internal build continues monotonically (`35` for this candidate). Existing build 32/34 clients therefore identify 1.0 as newer. Historical three-component versions remain supported as build inputs and are not renamed or republished. Workbench component 0.3.9 is unchanged.

**Verified:** 231 native tests passed, including four consent/update-flow tests. The appcast test passed. The complete ZIP, DMG and candidate App match all 470 files and pass strict code-signature validation. Original non-workbench resources are preserved. The candidate feed has a signed installable 1.0/build35 enclosure, localized notes and retained historical compatibility entries. It has not been uploaded to the production update URL.

Tests used the actual published 0.4.11 ZIP (SHA256 `607d9569405fc2b67cdd506ab016c1b3877b1bb002d454f657cc5a238b4be36a`). Its executable code was preserved; only bundle identifiers, test feed/public key, preference isolation and the resulting ad-hoc signature were changed. The two-argument test feed used ephemeral keys, deleted before launch. Preferences were seeded before the first launch. These are isolated update tests, not a production network upgrade or another user's Mac.

- Chinese and English old-client windows visibly showed Install Update, version 0.4.11 → 1.0, and normally formatted notes.
- Remind Me Later left the old app's files, language, scale and preference sentinel unchanged.
- A deliberately corrupted archive was rejected before extraction; its old app's 470 files and settings were unchanged.
- A valid archive downloaded, verified and extracted. Final replacement blocked inside the system rename operation. Installation and relaunch did **not** pass.
- Moving the test installation outside Desktop did not resolve the final replacement. An experiment using a restrictive update policy caused Sparkle to choose its legacy move/rollback path; that also blocked at system rename. This experiment was reverted and is **not** in the candidate. No system security mechanism was disabled.
- The actual desktop 0.4.13 App remains unchanged, matching its original 470 files.

[Chinese old-client prompt](update-0411-zh.png) · [English old-client prompt](update-0411-en.png) · [Corrupt archive rejection](corrupt-update-rejected.png) · [Machine-readable result](validation.json)

**Unverified:** Successful final replacement and relaunch on this Mac; production old-client upgrade; other Macs; Windows; Intel workbench; multi-day use; Apple notarization. The Mac is still on the same boot session as the previous installation failure. A reboot has been requested as a diagnostic next step, not presented as a proven fix. No 1.0 release or production feed has been published while this gate remains open.

**Issues:** 0.4.13's compiled download-page-only driver cannot be changed by a new feed. Once 1.0 is released, those users must install the complete 1.0 app in the same location once, then future in-app updates become available. Older 0.4.11/0.4.12 use the standard driver and can receive an installable feed item; their successful installation still requires final verification. Old 0.4.11 can ask for Install and Relaunch after downloading, while 1.0 carries the one-cycle consent forward. This is a compatibility behavior, not a reason to fake the old binary during testing.

**Next Steps:** Save work and reboot the entire Mac, rerun an actual 0.4.11 → 1.0 upgrade, verify relaunch and retained preferences, then publish the verified source and packages, update the sole desktop App, and verify public downloads against it. Keep Windows optional.

References: [Sparkle publishing and informational updates](https://sparkle-project.org/documentation/publishing/), [update safety and automatic-download settings](https://sparkle-project.org/documentation/customization/), [Sparkle 2.10 replacement logic](https://github.com/sparkle-project/Sparkle/blob/2.10.0/Autoupdate/SUPlainInstaller.m). These references explain the implementation; the failed install result above comes from the local tests.
