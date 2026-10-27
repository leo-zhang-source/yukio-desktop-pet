# Mac 5.3 workbench startup repair

## Report and reproduction

A user running the downloaded 5.3 (36) on an Apple silicon Mac with macOS 27.0.1 reported the native workbench startup error. Their supplied diagnostic report showed a Python listener on TCP 8767, a valid App signature, and successful startup of the same packaged runtime on two free ports, both with an empty profile and with the existing profile. The report did not include conversation contents or model configuration.

The original launcher reproduced the failure when the preferred port belonged to a different workbench or an unrelated TCP listener. It exited instead of opening another loopback port. The native host only accepted the literal 8767 URL and discarded startup errors, so Reconnect could repeat the same failure indefinitely.

## Repair

- The Mac host opts into `--fallback-port`. The launcher retains strict build/profile matching for reuse, and otherwise lets the OS atomically reserve a free loopback port when the preferred port is occupied. Existing owners and recorder leases are preserved. Explicit CLI port use without the flag remains strict.
- An explicit readiness message delivers the actual URL. The native host and navigation policy accept only that loopback origin; arbitrary log lines containing a URL do not indicate readiness.
- Startup failures retain safe diagnostic codes. No private configuration, paths or chat text are copied into the UI diagnostics. Silent startup has a timeout. Reconnect cancels the failed attempt and starts again. Failed page navigation also exposes Reconnect.
- A standalone Mac diagnostic script tests the installed runtime with empty and existing profiles on free ports. It does not collect chats, call a model, edit settings, disable protections, or stop an existing process.

## Verification

- 236 backend tests passed, including occupied foreign ports, different workbench identity, same-service reuse and invalid-configuration diagnostics.
- 240 native tests passed in the final serial run, including split readiness output, immediate reuse/exit, error and timeout paths, retry, diagnostic UI, and navigation restrictions. Earlier UI test attempts did not complete; those runs are not counted as passes. The final unit tests do not activate an AppKit window outside the native integration check.
- The frozen Mac runtime passed the existing package check: no system Python, Unicode/space paths, synthetic collectors, handoffs, history preservation across restart, process cleanup and source manifest hashes. No real model request was made.
- The actual native window loaded the bundled service on port 57631 while the installed 5.3 service retained 8767. Both the page and API connected. Switching to Settings and back kept the same page. The generated screenshot was inspected and shows “Connected · Waiting for chat.”

## Delivery scope

This is a separate Mac connection repair candidate, retaining the public label **5.3** with internal build **36.1** so it can be distinguished from public build 36. It is not a newly announced public version. Install it by quitting Yukio and replacing the existing App in the same Applications location. Preferences and histories live outside the App bundle. Future public builds with a higher build number can still update it.

The public GitHub release/feed and the developer's installed App have not been replaced by this repair task. The affected user's confirmation after installing the repair package remains pending. Windows, other macOS versions and Apple notarization are not newly verified. Final package checks and hashes are recorded in the local delivery receipt.
