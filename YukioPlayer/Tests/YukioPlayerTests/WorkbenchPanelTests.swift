import AppKit
import Testing
import WebKit
import YukioCore
@testable import YukioPlayer

@Suite @MainActor struct WorkbenchPanelTests {
    @Test func selectedDisplayModeSurvivesRecreatingTheAppController() throws {
        _ = NSApplication.shared
        let catalog = try AnimationCatalog.load(assetsRoot: SkinTests.root)
        let library = try SpriteLibrary(catalog: catalog, assetsRoot: SkinTests.root)
        let suite = "local.yukio.workbench-display-tests." + UUID().uuidString
        let defaults = try #require(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        func controller(_ preferences: UserDefaults) -> AppController {
            AppController(catalog: catalog, library: library, defaults: preferences, bundledAssets: SkinTests.root)
        }
        #expect(controller(defaults).workbenchDisplayForCheck() == .quickLook)
        for mode in WorkbenchDisplayMode.allCases {
            #expect(controller(defaults).workbenchDisplayForCheck(selecting: mode) == mode)
            #expect(defaults.synchronize())
            let reloaded = try #require(UserDefaults(suiteName: suite))
            #expect(controller(reloaded).workbenchDisplayForCheck() == mode)
        }
    }

    @Test func missingOrUnknownDisplayPreferenceKeepsExistingQuickViewBehavior() {
        #expect(WorkbenchDisplayMode(preference: "fullScreen") == .window)
        #expect(WorkbenchDisplayMode(preference: nil) == .quickLook)
        #expect(WorkbenchDisplayMode(preference: "unknown-future-value") == .quickLook)
        for mode in WorkbenchDisplayMode.allCases {
            #expect(WorkbenchDisplayMode(preference: mode.rawValue) == mode)
        }
    }

    @Test func displayChoicesAreLocalizedAndSendTheSelectedMode() throws {
        _ = NSApplication.shared
        let panel = SettingsPanelController()
        defer { panel.close() }
        let root = try #require(panel.window?.contentView)
        let popup = try #require(find(root, "workbenchDisplayPicker", as: NSSegmentedControl.self))
        let hint = try #require(find(root, "workbenchDisplayHint", as: NSTextField.self))
        var received: WorkbenchDisplayMode?
        panel.onChange = { if case .workbenchDisplayMode(let mode) = $0 { received = mode } }
        for language in [UILanguage.chinese, .english] {
            panel.presentationLanguage = language
            for mode in WorkbenchDisplayMode.allCases {
                var value = snapshot
                value.workbenchDisplayMode = mode
                panel.apply(value)
                #expect(popup.trackingMode == .selectOne)
                let segments = Array(0..<popup.segmentCount)
                #expect(segments.map { popup.label(forSegment: $0) ?? "" } == (language == .chinese
                    ? ["常驻窗口", "快速查看"] : ["Keep open", "Quick view"]))
                #expect(segments.filter { popup.isSelected(forSegment: $0) } == [popup.selectedSegment])
                #expect(WorkbenchDisplayMode.allCases[popup.selectedSegment] == mode)
                #expect(!hint.stringValue.isEmpty)
                if language == .english { #expect(hint.stringValue.range(of: "[\\p{Han}]", options: .regularExpression) == nil) }
                received = nil
                _ = popup.sendAction(popup.action, to: popup.target)
                #expect(received == mode)
            }
        }
    }

    @Test func changingWindowHostKeepsTheEmbeddedContentAndNormalWindowControls() throws {
        _ = NSApplication.shared
        let runtime = Runtime()
        let panel = WorkbenchPanelController(runtime: runtime)
        defer { panel.shutdown(); panel.close() }
        panel.apply(snapshot)
        panel.showSettings()
        let content = try #require(panel.window?.contentView)
        let settings = panel.settings.embeddedView()
        for mode in [WorkbenchDisplayMode.window, .quickLook, .window, .quickLook] {
            var value = snapshot
            value.workbenchDisplayMode = mode
            panel.apply(value)
            let host = try #require(panel.window)
            #expect(host.contentView === content)
            #expect(settings.window === host && panel.showingSettings)
            #expect(host.styleMask.contains(.nonactivatingPanel) == (mode == .quickLook))
            #expect(host.styleMask.contains(.miniaturizable) == (mode != .quickLook))
            if mode == .window {
                #expect(host.standardWindowButton(.zoomButton) != nil)
                #expect(!host.styleMask.contains(.fullScreen))
            }
            #expect(host.level == (mode == .quickLook ? .floating : .normal))
            #expect(host.collectionBehavior.contains(.fullScreenPrimary) == (mode != .quickLook))
            #expect(host.collectionBehavior.contains(.canJoinAllSpaces) == (mode == .quickLook))
        }
        #expect(runtime.starts == 0)
    }

    @Test func thePageCanOnlyNameAClientAndAPlainSessionToOpen() {
        let page = URL(string: "http://127.0.0.1:8767/?lang=zh")
        let id = "0A1B2C3D-0000-4000-8000-00000000ABCD"
        func parse(_ body: Any, _ url: URL? = page, main: Bool = true) -> WorkbenchChatTarget? {
            WorkbenchChatTarget.parse(body, frameURL: url, isMainFrame: main, port: 8767)
        }
        #expect(parse(["client": "claude", "session": id]) == WorkbenchChatTarget(client: .claude, session: id.lowercased()))
        #expect(parse(["client": "codex", "session": id])?.client == .codex)
        #expect(parse(["client": "deepcode", "session": id]) == nil)
        #expect(parse(["client": "claude", "session": id + "/../x"]) == nil)
        #expect(parse(["client": "claude", "session": "local_" + id]) == nil)
        #expect(parse(["client": "claude", "session": id, "url": "claude://anything"]) == nil)
        #expect(parse(["client": "claude", "session": 7]) == nil)
        #expect(parse("claude://code/continue?session=local_x") == nil)
        #expect(parse(["client": "claude", "session": id], main: false) == nil)
        #expect(parse(["client": "claude", "session": id], URL(string: "https://example.com/")) == nil)
        #expect(parse(["client": "claude", "session": id], URL(string: "http://127.0.0.1:9999/")) == nil)
        #expect(parse(["client": "claude", "session": id], nil) == nil)
    }

    @Test func openingAChatReportsWhetherTheAppCouldJump() {
        _ = NSApplication.shared
        let panel = WorkbenchPanelController(runtime: Runtime())
        defer { panel.shutdown(); panel.close() }
        var value = snapshot
        value.workbenchDisplayMode = .window
        panel.apply(value)
        let page = URL(string: "http://127.0.0.1:8767/")
        let body: [String: Any] = ["client": "claude", "session": "0a1b2c3d-0000-4000-8000-00000000abcd"]
        #expect(!panel.openChat(requestedBy: body, frameURL: page, isMainFrame: true))
        var asked: [WorkbenchChatTarget] = []
        var answer = true
        panel.onOpenChat = { asked.append($0); return answer }
        #expect(panel.openChat(requestedBy: body, frameURL: page, isMainFrame: true))
        answer = false
        #expect(!panel.openChat(requestedBy: body, frameURL: page, isMainFrame: true))
        #expect(!panel.openChat(requestedBy: ["client": "claude"], frameURL: page, isMainFrame: true))
        #expect(asked == Array(repeating: WorkbenchChatTarget(client: .claude, session: "0a1b2c3d-0000-4000-8000-00000000abcd"), count: 2))
    }

    /// The shipped page code, in the real page view, reaches the app and reads its answer.
    @Test func theShippedPageScriptReachesTheAppThroughTheRealPageView() async throws {
        _ = NSApplication.shared
        let panel = WorkbenchPanelController(runtime: Runtime())
        defer { panel.shutdown(); panel.close() }
        var value = snapshot
        value.workbenchDisplayMode = .window
        panel.apply(value)
        var asked: [WorkbenchChatTarget] = []
        var answer = true
        panel.onOpenChat = { asked.append($0); return answer }
        let web = panel.makeWebView()
        final class Loaded: NSObject, WKNavigationDelegate {
            var done: CheckedContinuation<Void, Never>?
            func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { done?.resume(); done = nil }
        }
        let loaded = Loaded()
        web.navigationDelegate = loaded
        await withCheckedContinuation { continuation in
            loaded.done = continuation
            web.loadHTMLString("<!doctype html><p id=alert hidden></p>", baseURL: URL(string: "http://127.0.0.1:8767/"))
        }
        let session = "0a1b2c3d-0000-4000-8000-00000000abcd"
        let key = try #require(String(data: JSONSerialization.data(withJSONObject: ["source", 1, session, "", 0]), encoding: .utf8))
            .data(using: .utf8)!.base64EncodedString()
            .replacingOccurrences(of: "+", with: "-").replacingOccurrences(of: "/", with: "_").replacingOccurrences(of: "=", with: "")
        let script = try String(contentsOf: URL(fileURLWithPath: #filePath).deletingLastPathComponent()
            .appendingPathComponent("../../../tools/activity-workbench/dist/glance.js").standardizedFileURL, encoding: .utf8)
        func part(_ head: String) throws -> String {
            let start = try #require(script.range(of: "\n" + head))
            let end = try #require(script.range(of: "\n}\n", range: start.upperBound..<script.endIndex))
            return String(script[start.lowerBound..<end.upperBound])
        }
        let page = try """
            var synthetic=false,current={client:'claude',key:'\(key)'};
            const $=id=>document.getElementById(id),tr=value=>value;
            function note(text){$('alert').textContent=text;$('alert').hidden=!text;}
            \(part("function openChatTarget("))\(part("async function openCurrentChat("))
            """
        _ = try await web.callAsyncJavaScript(page + "globalThis.pressOpenChat=openCurrentChat;return 1", contentWorld: .page)
        func press() async throws -> Bool {
            let hidden = try await web.callAsyncJavaScript("await pressOpenChat();return document.getElementById('alert').hidden", contentWorld: .page)
            return try #require(hidden as? Bool)
        }
        #expect(try await press())
        answer = false
        #expect(try await !press())
        #expect(asked == Array(repeating: WorkbenchChatTarget(client: .claude, session: session), count: 2))
        let handled = try await web.callAsyncJavaScript(
            "return await webkit.messageHandlers.yukioOpenChat.postMessage({client:'claude',session:'x'})", contentWorld: .page)
        #expect(handled as? Bool == false)
        #expect(asked.count == 2)
    }

    @Test func onlyExactOfficialSetupLinksCanLeaveWorkbench() throws {
        for value in ["https://learn.chatgpt.com/docs/codex/cli", "https://code.claude.com/docs/en/setup"] {
            #expect(WorkbenchPanelController.isAssistantSetupLink(try #require(URL(string: value))))
        }
        for value in ["http://learn.chatgpt.com/docs/codex/cli", "https://learn.chatgpt.com.evil.invalid/docs/codex/cli",
                      "https://code.claude.com/docs/en/setup?redirect=private", "file:///Users/test/private"] {
            #expect(!WorkbenchPanelController.isAssistantSetupLink(try #require(URL(string: value))))
        }
    }
    @Test func explicitAppLanguageWinsAndSwitchingRefreshesTheWholeWorkbench() throws {
        _ = NSApplication.shared
        #expect(WorkbenchPanelController.preferredLanguage(["zh-Hans"], appPreference: "en") == "en")
        #expect(WorkbenchPanelController.preferredLanguage(["en-US"], appPreference: "zh") == "zh")
        #expect(WorkbenchPanelController.preferredLanguage(["zh-Hans"]) == "zh")
        let runtime = Runtime()
        let panel = WorkbenchPanelController(runtime: runtime, preferredLanguages: ["zh-Hans"])
        defer { panel.shutdown(); panel.close() }
        panel.apply(snapshot); panel.showSettings()
        panel.setLanguage(.english); panel.apply(snapshot)
        #expect(panel.showingSettings && panel.uiLanguage == "en")
        #expect(panel.window?.title == "Yukio · Activity workbench")
        let root = try #require(panel.window?.contentView)
        #expect(try #require(find(root, "workbenchTab", as: NSButton.self)).title == "Activity workbench")
        #expect(try #require(find(root, "petSettingsTab", as: NSButton.self)).title == "Settings")
        #expect(runtime.starts == 0)
        let url=panel.localizedURL(URL(string: "http://127.0.0.1:8767/?client=codex&key=preserved&lang=zh")!)
        #expect(url.query?.contains("key=preserved") == true && url.query?.contains("lang=en") == true)
    }
    @Test func embeddedEnglishSettingsDoNotFollowThePetsChinesePreference() throws {
        _ = NSApplication.shared
        let saved = L10n.language
        L10n.language = .chinese
        defer { L10n.language = saved }
        let app = WorkbenchPanelController(runtime: Runtime(), preferredLanguages: ["en-US"])
        defer { app.shutdown(); app.close() }
        app.apply(snapshot)
        let root = try #require(app.window?.contentView)
        let settings = try #require(find(root, "petSettingsTab", as: NSButton.self))
        settings.performClick(nil)
        let headings = try ["appearanceSettingsHeading", "chatSettingsHeading", "generalSettingsHeading"].map {
            try #require(find(root, $0, as: NSTextField.self)).stringValue
        }
        #expect(headings == ["Appearance", "Chats & notices", "General"])
        #expect(try #require(find(root, "hideWhenIdleSwitch", as: NSSwitch.self)).toolTip == "Hide while idle and appear when working or showing a notice.")
        #expect(L10n.language == .chinese)
        #expect(L10n.stateName(.verify, in: .english) == "Running tests")
    }
    private final class Runtime: WorkbenchStarting {
        var starts = 0, stops = 0
        var pending: ((Result<URL, Error>) -> Void)?
        func start(_ completion: @escaping (Result<URL, Error>) -> Void) { starts += 1; pending = completion }
        func stop() { stops += 1 }
        func ready() { pending?(.success(URL(string: "http://127.0.0.1:8767/native-test-page")!)) }
    }
    private var snapshot: SettingsSnapshot {
        SettingsSnapshot(status: "正在工作", following: true, hidden: false, provider: .auto, chats: [],
                         showBubble: true, showCards: true, showQuestionCard: true, scale: 1,
                         language: .chinese, demoPlaying: false)
    }
    private func find<T: NSView>(_ view: NSView, _ identifier: String, as: T.Type) -> T? {
        if view.accessibilityIdentifier() == identifier { return view as? T }
        return view.subviews.compactMap { find($0, identifier, as: T.self) }.first
    }

    @Test func workAndSettingsUseOneWindowAndPreserveExistingActions() throws {
        _ = NSApplication.shared
        let runtime = Runtime()
        let app = WorkbenchPanelController(runtime: runtime)
        defer { app.shutdown(); app.close() }
        app.apply(snapshot)
        let host = try #require(app.window)
        let settingsButton = try #require(find(host.contentView!, "petSettingsTab", as: NSButton.self))
        settingsButton.performClick(nil)
        #expect(app.showingSettings)
        let toggle = try #require(find(host.contentView!, "hideWhenIdleSwitch", as: NSSwitch.self))
        #expect(toggle.window === host)
        #expect(app.settings.window?.isVisible == false)
        var changed: Bool?
        app.onChange = { if case .hideWhenIdle(let value) = $0 { changed = value } }
        toggle.performClick(nil)
        #expect(changed == false)
        let workButton = try #require(find(host.contentView!, "workbenchTab", as: NSButton.self))
        workButton.performClick(nil)
        #expect(!app.showingSettings)
        #expect(runtime.starts == 1)
        app.close()
        #expect(app.webView == nil && host.isVisible == false)
        // Closing the panel must not stop a recorder owned by this app, or another app.
        #expect(runtime.stops == 0)
    }

    @Test func missingRuntimeDoesNotFallBackToASystemInterpreter() {
        let runtime = WorkbenchRuntime(resources: URL(fileURLWithPath: "/nonexistent-yukio-test"))
        var failed = false
        runtime.start { if case .failure = $0 { failed = true } }
        #expect(failed)
        runtime.stop()
    }

    @Test func workbenchFollowsSystemLanguageWithoutChangingPetPreferences() throws {
        _ = NSApplication.shared
        #expect(WorkbenchPanelController.preferredLanguage(["zh-Hans-CN", "en-US"]) == "zh")
        #expect(WorkbenchPanelController.preferredLanguage(["en-GB", "zh-Hans"]) == "en")
        #expect(WorkbenchPanelController.preferredLanguage(["fr-FR"]) == "en")
        let panel = WorkbenchPanelController(runtime: Runtime(), preferredLanguages: ["en-US"])
        defer { panel.shutdown(); panel.close() }
        panel.apply(snapshot) // Pet's manual language can differ from the system.
        #expect(panel.uiLanguage == "en")
        #expect(panel.window?.title == "Yukio · Activity workbench")
        let button = try #require(find(panel.window!.contentView!, "petSettingsTab", as: NSButton.self))
        #expect(button.title == "Settings")
        let url = panel.localizedURL(URL(string: "http://127.0.0.1:8767/?client=codex&key=chat&lang=zh")!)
        let query = URLComponents(url: url, resolvingAgainstBaseURL: false)!.queryItems!
        #expect(query.filter { $0.name == "lang" }.map(\.value) == ["en"])
        #expect(query.contains { $0.name == "key" && $0.value == "chat" })
    }

    @Test func unavailableWorkbenchKeepsSettingsUsableAndOnlyLocalNavigationIsAllowed() throws {
        _ = NSApplication.shared
        let runtime = Runtime(), panel = WorkbenchPanelController(runtime: runtime)
        defer { panel.shutdown(); panel.close() }
        panel.apply(snapshot)
        panel.showWork()
        runtime.pending?(.failure(WorkbenchRuntime.Failure.unavailable))
        panel.showSettings()
        #expect(panel.showingSettings)
        #expect(find(panel.window!.contentView!, "lowerSignButton", as: NSButton.self) != nil)
        #expect(WorkbenchPanelController.isLocal(URL(string: "http://127.0.0.1:8767/history")!))
        for address in ["https://example.com", "file:///etc/passwd", "http://127.0.0.1:9999/", "http://user@127.0.0.1:8767/"] {
            #expect(!WorkbenchPanelController.isLocal(URL(string: address)!))
        }
    }
}
