import AppKit
import Testing
import WebKit
import YukioCore
@testable import YukioPlayer

@Suite @MainActor struct WorkbenchPanelTests {
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
        let picker = try #require(find(root, "settingsCategoryPicker", as: NSSegmentedControl.self))
        #expect((0..<picker.segmentCount).compactMap { picker.label(forSegment: $0) } == ["Appearance", "Chats & notices", "More"])
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
