# Workbench language and understandable context

Mac 0.4.10 embeds workbench 0.3.7. The native workbench uses the first macOS preferred language: Chinese variants share the Chinese UI; English and unsupported languages use English. The page receives that choice, and standalone browser use follows the browser language. Reopening the App after changing the system language applies the new preference. The pet's existing manual language preference is not overwritten.

The page, loading/error messages, navigation and model explanations use the same language. Chat titles, user requests and quoted source notes remain in their original language; the model writes the explanation in the selected UI language. A temporary local note never pretends to translate an arbitrary source message without a model.

## What changed

- The chat sidebar uses Projects above Recent chats. Search and project expansion stay local. Working, waiting, ended and unknown are per-chat markers, never navigation categories; no selection or model send is triggered by searching.
- Real-chat review of 0.4.8 found an unrelated illustration copied from the writing instructions into the project explanation. Those concrete domain examples have been removed. Current action and request take precedence over old plans; quoted examples and test subjects cannot establish project facts. A local outcome suffix is no longer included in the model’s action excerpt and then appended again.


- A clipped tool response containing boolean fields and a partial object could become the explanation paragraph. Only conversational fragments may now supply that local paragraph. Presentation filtering removes code, commands, paths, filenames, addresses and internal identifiers without changing the saved history or the private evidence used for matching.
- Supporting notes in the workbench use readable descriptions. The older record view no longer prints raw metadata tables or a JSON prompt dump. Exact IDs remain inside the local data and request matching, rather than becoming prose.
- Home explanations no longer share a 100-character ceiling. Content remains compact; context and purpose have separate, bounded budgets. Chinese targets are roughly 40–90 / 100–180 / 80–150 characters; English targets are 20–45 / 55–100 / 40–85 words. These are writing targets, not a proof of comprehension.
- Ordinary chats now provide their earlier readable request and most recent public checkpoint as writing anchors. A hand-written project brief is not required. The model must explain what an object does, what earlier work was reported, what changed now and why the step helps the user.
- English uses its own plain-language instructions and outcome wording. Earlier assistant claims stay attributed, closed turns cannot be described as running, and results are not assigned to a different operation.
- Filtering distinguishes ordinary English such as “let the app find videos” from a variable declaration. The original broad rule incorrectly removed part of such sentences; the regression is covered.

## Boundaries

Only the selected chat's bounded public excerpts are used. This change adds no destination, paid service, whole-chat export, hidden-reasoning access or background model scheduler. The hourly call limit and minimum refresh interval remain; longer explanations have a bounded output budget. Close/switch cancellation and the page lease remain in place.

Neither a word budget nor reference validation proves that an explanation is correct or easy to understand. Missing context must stay unknown; a filename cannot establish a file's purpose. Chinese and English example-isolation checks use an explicitly simulated workbench task containing an unrelated example. A bounded excerpt from the current real Yukio chat is checked separately. This checks those cases, not every possible summary. Windows remains optional and untested for this release.

## Native update boundary in 0.4.10

The standard Sparkle UI replaces the custom immediate-install callback. A signed loopback-only test reached the final install prompt and terminated the test host, but the helper remained inside `renamex_np` while replacing the test App directory. This also happened with the standard driver, so the custom callback is not established as the root cause. No trust checks or macOS protections were disabled. Automatic replacement remains unverified; the desktop is retained at the intact, verified 0.4.9. This 0.4.10 candidate is not published; a clean restart/retest is still needed.
