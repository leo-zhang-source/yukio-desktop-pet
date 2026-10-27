# Yukio 1.0 — update verification

**Implemented:** Restore an installable signed feed, maintained localized update UI and readable short English/Chinese notes. An explicit Install Update choice authorizes one download/install/relaunch cycle. Background checks do not authorize silent installation. Signed-feed validation, archive verification before extraction, opt-out and the six-hour check schedule remain. Disable the sandbox-only installer launcher: this app has no sandbox entitlement, and Sparkle explicitly says not to enable that service for non-sandboxed hosts.

**Version policy:** Public versions use 1.0, 1.1, 1.2, then 2.0 for a major release. Internal build 35 remains monotonic; historical three-component versions are still accepted and are not relabeled. Workbench 0.3.9 is unchanged.

**Verified:** 231 native tests (four consent-flow tests included), one appcast test and eight progress-site checks. Candidate ZIP, DMG and the sole desktop App match 470 files. Old history prefixes, all three private configurations and the native language preference remain intact. Workbench's 233 backend and 28 page checks are the unchanged prior baseline, not newly rerun tests.

- Used the actual published 0.4.11 ZIP, SHA256 `607d9569405fc2b67cdd506ab016c1b3877b1bb002d454f657cc5a238b4be36a`. Its executable code was preserved; only isolation metadata, test feed/public key and the resulting ad-hoc signature changed. Temporary test keys were deleted before launch.
- Chinese and English windows showed Install Update and normally formatted notes. Later preserved the old App and settings. A deliberately corrupted archive was rejected, leaving all old files and settings unchanged.
- After a confirmed full reboot, the Desktop test still waited in system rename. System logs showed a Desktop-folder permission prompt pending. Reboot alone was not a fix, and the earlier restrictive-policy experiment did not fix it either; that policy was reverted. No system protection was bypassed.
- Paused the pending Desktop trial and used a non-Desktop test installation. The actual old **0.4.11 → 1.0** downloaded, installed and relaunched after the Install Update click; all **470 target files**, strict signatures, language, scale and a pre-launch preference sentinel matched. [Result](old-release-upgrade.json).
- A distinct, explicitly simulated **1.0 → 1.1** future update also completed after one click and preserved the same settings. **1.1 is not a public release.** [Result](future-upgrade.json).
- The read-only verifier inspects files, preferences and the running executable without reopening a host that has exited during installation. Earlier UI polling could reopen the old host during replacement, so it is not used as an installation-success signal.

[Chinese prompt](update-0411-zh.png) · [English old-release prompt](update-0411-en.png) · [Simulated future update](future-update-test.png) · [Corrupt archive rejection](corrupt-update-rejected.png) · [Package checks](validation.json)

**Unverified / limits:** Successful in-app replacement on Desktop without user folder authorization; other Macs; Windows; Intel workbench; multi-day use; Apple notarization. Successful isolated installs used this Mac's user Applications directory, not another customer's computer. This is an ad-hoc signed Mac release. Folder permission prompts require the user's own response; full disk access is not required.

**Migration issue:** 0.4.13's compiled download-page-only driver cannot be retrofitted by a feed. Those users must install the full 1.0 package once in the same location, then in-app updates resume. The developer's Desktop App takes this same one-time migration; it is not falsely reported as a 0.4.13 in-app upgrade.

**Delivery checks:** The package checks record the tested source and resource hashes. The final delivery also verifies the public GitHub asset digests/downloads and production feed, and updates the progress website. Temporary bundles are stopped, unregistered and archived; only the canonical Yukio remains installed. Windows's old compatible files remain unchanged and optional.

**Next Steps:** Broader optional Mac/Windows testing, long-term use and proper Developer ID/notarization. No further Windows testing is required for this Mac delivery.

References: [Sparkle configuration](https://sparkle-project.org/documentation/customization/), [publishing updates](https://sparkle-project.org/documentation/publishing/), [Sparkle 2.10 replacement code](https://github.com/sparkle-project/Sparkle/blob/2.10.0/Autoupdate/SUPlainInstaller.m). Runtime conclusions above come from the recorded local tests, not these references.
