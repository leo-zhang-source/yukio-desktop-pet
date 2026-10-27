import AppKit
import Testing
import YukioCore
@testable import YukioPlayer

@Suite @MainActor struct SettingsLayoutTests {
    private func find<T: NSView>(_ view: NSView, _ id: String, as: T.Type) -> T? {
        if view.accessibilityIdentifier() == id { return view as? T }
        return view.subviews.compactMap { find($0, id, as: T.self) }.first
    }
    private func hidden(_ view: NSView) -> Bool {
        var node: NSView? = view
        while let current = node { if current.isHidden { return true }; node = current.superview }
        return false
    }
    @Test(arguments: [UILanguage.chinese, .english])
    func overviewShowsEveryGroupAndAdaptsWithoutChangingPreferences(language: UILanguage) throws {
        _ = NSApplication.shared
        let controller = SettingsPanelController()
        defer { controller.close() }
        let chat = SessionSummary(id: "layout-check", title: String(repeating: "Long conversation title · ", count: 12),
            state: .default_work, live: true, raisedSign: false, quietMs: 0, focused: true, pinned: true)
        let snapshot = SettingsSnapshot(status: "正在工作", following: true, hidden: false, provider: .auto,
            chats: [chat], showBubble: true, showCards: false, showQuestionCard: true, scale: 1.2,
            language: language, demoPlaying: false, launchAtLogin: .requiresApproval)
        controller.apply(snapshot)
        let root = try #require(controller.window?.contentView)
        #expect(find(root, "settingsCategoryPicker", as: NSSegmentedControl.self) == nil)
        let sign = try #require(find(root, "lowerSignButton", as: NSButton.self))
        let browser = try #require(find(root, "browserChatPermissionButton", as: NSButton.self))
        let startup = try #require(find(root, "launchAtLoginSwitch", as: NSSwitch.self))
        let idle = try #require(find(root, "hideWhenIdleSwitch", as: NSSwitch.self))
        #expect(!hidden(sign) && !hidden(browser) && !hidden(startup))
        let initial = idle.state
        for width: CGFloat in [1100, 760, 540, 1400, 1050] {
            controller.window?.setContentSize(NSSize(width: width, height: 650))
            controller.apply(snapshot)
            root.layoutSubtreeIfNeeded()
            root.layoutSubtreeIfNeeded()
            let document = controller.embeddedView()
            let groups = try ["appearanceSettingsGroup", "chatSettingsGroup", "generalSettingsGroup"].map {
                try #require(find(root, $0, as: NSStackView.self))
            }
            let frames = groups.map { $0.convert($0.bounds, to: document) }
            #expect(groups.allSatisfy { !hidden($0) })
            #expect(frames.allSatisfy { document.bounds.contains($0) && $0.width > 250 })
            #expect(!frames[0].intersects(frames[1]) && !frames[1].intersects(frames[2]))
            #expect(idle.state == initial)
            if width >= 1000 {
                #expect(abs(frames[0].minY - frames[2].minY) < 1)
                #expect(frames[2].maxX > width - 30)
                for control in [sign as NSView, browser as NSView, startup as NSView] {
                    #expect(root.bounds.contains(control.convert(control.bounds, to: root)))
                }
            }
        }
        var cancelled = 0
        controller.onChange = { if case .lowerSign = $0 { cancelled += 1 } }
        sign.performClick(nil)
        #expect(cancelled == 1)
    }
}
