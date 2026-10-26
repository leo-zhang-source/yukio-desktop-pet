# Workbench language and understandable context

Mac 0.4.8 embeds workbench 0.3.6. The native workbench uses the first macOS preferred language: Chinese variants share the Chinese UI; English and unsupported languages use English. The page receives that choice, and standalone browser use follows the browser language. Reopening the App after changing the system language applies the new preference. The pet's existing manual language preference is not overwritten.

The page, loading/error messages, navigation and model explanations use the same language. Chat titles, user requests and quoted source notes remain in their original language; the model writes the explanation in the selected UI language. A temporary local note never pretends to translate an arbitrary source message without a model.

## What changed

- A clipped tool response containing boolean fields and a partial object could become the explanation paragraph. Only conversational fragments may now supply that local paragraph. Presentation filtering removes code, commands, paths, filenames, addresses and internal identifiers without changing the saved history or the private evidence used for matching.
- Supporting notes in the workbench use readable descriptions. The older record view no longer prints raw metadata tables or a JSON prompt dump. Exact IDs remain inside the local data and request matching, rather than becoming prose.
- Home explanations no longer share a 100-character ceiling. Content remains compact; context and purpose have separate, bounded budgets. Chinese targets are roughly 40–90 / 100–180 / 80–150 characters; English targets are 20–45 / 55–100 / 40–85 words. These are writing targets, not a proof of comprehension.
- Ordinary chats now provide their earlier readable request and most recent public checkpoint as writing anchors. A hand-written project brief is not required. The model must explain what an object does, what earlier work was reported, what changed now and why the step helps the user.
- English uses its own plain-language instructions and outcome wording. Earlier assistant claims stay attributed, closed turns cannot be described as running, and results are not assigned to a different operation.
- Filtering distinguishes ordinary English such as “let the app find videos” from a variable declaration. The original broad rule incorrectly removed part of such sentences; the regression is covered.

## Boundaries

Only the selected chat's bounded public excerpts are used. This change adds no destination, paid service, whole-chat export, hidden-reasoning access or background model scheduler. The hourly call limit and minimum refresh interval remain; longer explanations have a bounded output budget. Close/switch cancellation and the page lease remain in place.

Neither a word budget nor reference validation proves that an explanation is correct or easy to understand. Missing context must stay unknown; a filename cannot establish a file's purpose. Chinese and English were checked with explicitly simulated video-connection work, and the installed Mac is checked separately. Windows remains optional and untested for this release.
