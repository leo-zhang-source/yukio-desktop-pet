# Mac English presentation verification

**Implemented:** complete generated English UI, language selection shared by the pet/workbench, English native settings and launcher messages, dynamic result/handoff/recap translations, mixed-language model rejection. Actual chat names and original quotations retain their language.

**Verified:** 232 backend, 28 page, 227 native, 13 resource and seven window checks. Isolated packaged runtime checks passed without system Python. A bounded current-chat case produced three English model paragraphs. Desktop “Yukio English” has 470 files matching the ZIP and retains the original App. Old history prefixes and all three private configuration files were preserved.

**Unverified:** final full native workbench page review is blocked by macOS Screen Time. The English native header/controls were observed, but this is not substituted for an unblocked page review. Windows, other Macs, multi-day use and Apple notarization remain optional or unverified.

**Issues:** installation after clicking an update remains unaccepted and deferred; this release does not contain the separate 0.4.10 installer candidate. No security or Screen Time setting was changed.

**Next steps:** after the user independently handles the system time limit, review the full native page. Resume installer investigation only when requested.

See [validation.json](validation.json) for the package and desktop checks. Public evidence contains no chat excerpts or private configuration.
