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
    @Test func categoriesKeepTheSameControlsAndPreferences() throws {
        _ = NSApplication.shared
        let controller = SettingsPanelController()
        defer { controller.close() }
        let snapshot = SettingsSnapshot(status: "正在工作", following: true, hidden: false, provider: .auto,
            chats: [], showBubble: true, showCards: false, showQuestionCard: true, scale: 1.2,
            language: .chinese, demoPlaying: false)
        controller.apply(snapshot)
        let root = try #require(controller.window?.contentView)
        let picker = try #require(find(root, "settingsCategoryPicker", as: NSSegmentedControl.self))
        let sign = try #require(find(root, "lowerSignButton", as: NSButton.self))
        let browser = try #require(find(root, "browserChatPermissionButton", as: NSButton.self))
        let startup = try #require(find(root, "launchAtLoginSwitch", as: NSSwitch.self))
        let idle = try #require(find(root, "hideWhenIdleSwitch", as: NSSwitch.self))
        #expect(picker.segmentCount == 3 && !hidden(sign) && hidden(browser) && hidden(startup))
        let initial = idle.state
        for (index, visible) in [(1, browser as NSView), (2, startup as NSView), (0, sign as NSView)] {
            picker.selectedSegment = index
            NSApp.sendAction(try #require(picker.action), to: picker.target, from: picker)
            controller.apply(snapshot)
            #expect(!hidden(visible))
            #expect(picker.selectedSegment == index && idle.state == initial)
        }
        root.layoutSubtreeIfNeeded()
        #expect(root.frame.width >= 590 && root.frame.height < 850)
        var cancelled = 0
        controller.onChange = { if case .lowerSign = $0 { cancelled += 1 } }
        sign.performClick(nil)
        #expect(cancelled == 1)
    }
}
