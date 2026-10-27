# Mac 0.4.13 · Manual update verification

**Implemented:** Signed update checks, automatic reminders and manual download-page offers. The driver never returns Install; pending installer callbacks are skipped and unexpected downloads cancelled. Release feeds mark the newest Mac release informational, including for compatible older clients. English/Chinese notices and a settings tooltip explain the manual flow. Existing opt-out, scheduling and signed-feed settings remain.

**Verified:** 232 native tests passed, including five tests for trusted release URLs, both notice languages, Later, browser failure and cancelling old staged installation. The appcast test passed with informational marking, correct release link, signature metadata and retained architecture fallback. Two native signed-feed fixtures displayed the real production driver: Later kept the current version running; Open download page opened the official release in the default browser. The fixture server saw two feed requests and zero archive requests. Fixture Apps were archived and their processes stopped. ZIP, DMG and desktop match 470 files; signatures, history prefixes and all three private configuration files were checked. Workbench 0.3.9 is reused unchanged from 0.4.12; its 233 backend and 28 page checks are the prior baseline, not new test runs.

**Unverified:** Windows, other Macs, Intel workbench support, multi-day use and Apple notarization. An actual future public-version notification cannot be tested from the latest production version without a newer release; the signed newer-version fixtures cover that path.

**Issues:** This does not repair the old installer or perform an in-app replacement. The intended user flow is now manual download and replacement. The Mac package remains ad-hoc signed, not notarized. Temporary test keys were removed; no private profiles, recovery maps or test Apps are uploaded.

**Next Steps:** Use the reminder/manual-download flow for the next release; keep Windows and broader compatibility work optional.
