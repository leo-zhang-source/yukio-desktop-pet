import AppKit
import Testing
import YukioCore
@testable import YukioPlayer

/// Exercises the view's focus policy with real AppKit field editors and a
/// controlled key-window input. WindowServer focus acquisition is tested in the
/// installed App; a test runner cannot assume it owns the user's keyboard.
@MainActor private final class QuestionFocusFixture: NSPanel {
    let cardView = QuestionCardView(frame: .zero)
    var testIsKey = true
    override var isKeyWindow: Bool { testIsKey }
    override var canBecomeKey: Bool { true }

    init(size: NSSize) {
        super.init(contentRect: NSRect(origin: .zero, size: size),
                   styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
        isReleasedWhenClosed = false
        contentView = cardView
    }
}

@Suite @MainActor struct QuestionDraftTests {
    @Test func remindersUseTheirOwnSettingsWithoutMigratingOrChangingOtherKeys() throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: directory) }
        let aName = "local.yukio.reminder-a." + UUID().uuidString
        let bName = "local.yukio.reminder-b." + UUID().uuidString
        let a = try #require(UserDefaults(suiteName: aName)), b = try #require(UserDefaults(suiteName: bName))
        defer { a.removePersistentDomain(forName: aName); b.removePersistentDomain(forName: bName) }
        a.set(false, forKey: "assistantReminderSound"); b.set(true, forKey: "assistantReminderSound")
        a.set("keep", forKey: "unrelated")
        let first = ReminderStore(url: directory.appendingPathComponent("a.json"), defaults: a)
        let second = ReminderStore(url: directory.appendingPathComponent("b.json"), defaults: b)
        #expect(!first.soundEnabled && second.soundEnabled)
        b.set(false, forKey: "assistantReminderSound")
        #expect(!first.soundEnabled && !second.soundEnabled)
        #expect(a.string(forKey: "unrelated") == "keep")
    }

    @Test func startupUsesInjectedSettingsAndKeepsLegacyKeys() throws {
        let previousLanguage = L10n.language
        defer { L10n.language = previousLanguage }
        let root = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent("Resources/Assets")
        let catalog = try AnimationCatalog.load(assetsRoot: root)
        let library = try SpriteLibrary(catalog: catalog, assetsRoot: root)
        for (code, source, following, cards) in [("zh", "codex", false, true), ("en", "claude-code", true, false)] {
            let suite = "local.yukio.settings-tests." + UUID().uuidString
            let defaults = try #require(UserDefaults(suiteName: suite))
            defer { defaults.removePersistentDomain(forName: suite) }
            defaults.set(code, forKey: "language"); defaults.set(source, forKey: "source")
            defaults.set(following, forKey: "followClaude"); defaults.set(cards, forKey: "showCards")
            defaults.set("existing data", forKey: "unrelatedKey")
            let before = defaults.persistentDomain(forName: suite)! as NSDictionary
            let controller = AppController(catalog: catalog, library: library, defaults: defaults)
            let settings = controller.initialSettingsForCheck()
            #expect(settings.language == UILanguage(code: code))
            #expect(settings.provider == AgentProvider(code: source))
            #expect(settings.following == following && settings.cards == cards)
            #expect(before == defaults.persistentDomain(forName: suite)! as NSDictionary)
        }
    }

    @Test func escapeKeepsActiveDraftAndDoesNotSend() throws {
        _ = NSApplication.shared
        let panel = QuestionPanel()
        defer { panel.makeFirstResponder(nil); panel.close() }
        panel.cardView.card = QuestionCardLayout(PetQuestion(text: "Synthetic question", options: []), canOpenChat: false)
        panel.makeKeyAndOrderFront(nil)
        #expect(panel.makeFirstResponder(panel.cardView.field))
        let editor = try #require(panel.cardView.field.currentEditor() as? NSTextView)
        editor.insertText("  Yukio 你好123  ", replacementRange: NSRange(location: NSNotFound, length: 0))
        var closed = 0, sent = 0
        panel.cardView.onClose = { closed += 1 }
        panel.cardView.onSend = { _ in sent += 1 }
        #expect(panel.cardView.control(panel.cardView.field, textView: editor, doCommandBy: #selector(NSResponder.cancelOperation(_:))))
        #expect(closed == 1 && sent == 0)
        #expect(editor.string == "  Yukio 你好123  ")
        #expect(panel.cardView.draftText == editor.string)
        editor.setMarkedText("ni", selectedRange: NSRange(location: 2, length: 0), replacementRange: NSRange(location: NSNotFound, length: 0))
        #expect(editor.hasMarkedText())
        #expect(!panel.cardView.control(panel.cardView.field, textView: editor, doCommandBy: #selector(NSResponder.cancelOperation(_:))))
        #expect(!panel.cardView.control(panel.cardView.field, textView: editor, doCommandBy: #selector(NSResponder.insertNewline(_:))))
        #expect(closed == 1 && sent == 0)
    }

    @Test func inputDiagnosticsContainStateButNeverDraftOrChatIdentity() throws {
        _ = NSApplication.shared
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: directory) }
        let url = directory.appendingPathComponent("input.jsonl")
        let view = QuestionCardView(frame: .zero)
        view.inputDiagnostics = try #require(QuestionInputDiagnostics(url: url))
        view.field.stringValue = "SECRET ANSWER"
        view.diagnosticRequestID = "synthetic-request-1"
        view.recordInputState("state")
        view.recordInputState("state")
        let raw = try String(contentsOf: url)
        #expect(!raw.contains("SECRET"))
        #expect(raw.split(separator: "\n").count == 1)
        #expect(raw.contains("draft_length") && raw.contains("synthetic-request-1"))
        #expect(QuestionInputDiagnostics(url: url) == nil)
        let permissions = try FileManager.default.attributesOfItem(atPath: url.path)[.posixPermissions] as? NSNumber
        #expect(permissions?.intValue == 0o600)
    }

    @Test(arguments: 0..<10) func sendingAndFailureRetainTheActiveFieldEditorsDraft(attempt: Int) throws {
        _ = NSApplication.shared
        let panel = QuestionPanel()
        defer { panel.makeFirstResponder(nil); panel.close() }
        let question = PetQuestion(text: "Synthetic question", options: [])
        let normal = QuestionCardLayout(question, canOpenChat: false)
        panel.setContentSize(normal.size)
        panel.cardView.card = normal
        panel.alphaValue = 1
        panel.makeKeyAndOrderFront(nil)
        #expect(panel.makeFirstResponder(panel.cardView.field))
        let editor = try #require(panel.cardView.field.currentEditor() as? NSTextView)
        editor.insertText("Yukio 你好123", replacementRange: NSRange(location: NSNotFound, length: 0))
        #expect(editor.string == "Yukio 你好123")
        panel.cardView.card = QuestionCardLayout(question, canOpenChat: false, sentNotice: "Sending", isSending: true)
        #expect(!panel.cardView.field.isEnabled)
        #expect(panel.cardView.field.stringValue == "Yukio 你好123")
        panel.cardView.card = QuestionCardLayout(question, canOpenChat: false, sentNotice: "Failed; retry")
        #expect(panel.cardView.field.isEnabled)
        #expect(panel.cardView.answerText == "Yukio 你好123")
        #expect(panel.makeFirstResponder(panel.cardView.field))
        let retryEditor = try #require(panel.cardView.field.currentEditor() as? NSTextView)
        #expect(retryEditor.string == "Yukio 你好123")
    }
    @Test func failureRestoresOwnedEditorAndSelectionWithoutAnotherClick() throws {
        _ = NSApplication.shared
        let question = PetQuestion(text: "Synthetic question", options: [])
        let normal = QuestionCardLayout(question, canOpenChat: false)
        let panel = QuestionFocusFixture(size: normal.size)
        defer { panel.makeFirstResponder(nil); panel.close() }
        panel.cardView.card = normal
        panel.orderFront(nil)
        try #require(panel.isVisible && panel.isKeyWindow)
        #expect(panel.makeFirstResponder(panel.cardView.field))
        let editor = try #require(panel.cardView.field.currentEditor() as? NSTextView)
        editor.insertText("Yukio 你好123", replacementRange: NSRange(location: NSNotFound, length: 0))
        editor.setSelectedRange(NSRange(location: 11, length: 0))
        panel.cardView.card = QuestionCardLayout(question, canOpenChat: false, isSending: true)
        panel.cardView.card = QuestionCardLayout(question, canOpenChat: false, sentNotice: "Failed")
        let restored = try #require(panel.cardView.field.currentEditor() as? NSTextView)
        #expect(panel.firstResponder === restored)
        #expect(restored.selectedRange() == NSRange(location: 11, length: 0))
        restored.insertText("abc", replacementRange: NSRange(location: NSNotFound, length: 0))
        #expect(panel.cardView.draftText == "Yukio 你好123abc")
    }

    @Test func failureDoesNotStealFocusFromAnotherEditorOrNewQuestion() throws {
        _ = NSApplication.shared
        let question = PetQuestion(text: "Synthetic question", options: [])
        let normal = QuestionCardLayout(question, canOpenChat: false)
        let panel = QuestionFocusFixture(size: normal.size)
        defer { panel.makeFirstResponder(nil); panel.close() }
        panel.cardView.card = normal
        panel.orderFront(nil)
        try #require(panel.isVisible && panel.isKeyWindow)
        #expect(panel.makeFirstResponder(panel.cardView.field))
        panel.cardView.card = QuestionCardLayout(question, canOpenChat: false, isSending: true)
        let other = NSTextField(frame: NSRect(x: 0, y: 0, width: 60, height: 20))
        panel.cardView.addSubview(other)
        #expect(panel.makeFirstResponder(other))
        let otherEditor = try #require(other.currentEditor())
        panel.cardView.card = normal
        #expect(panel.firstResponder === otherEditor)
        #expect(panel.cardView.field.currentEditor() == nil)
        #expect(panel.makeFirstResponder(panel.cardView.field))
        panel.cardView.card = QuestionCardLayout(question, canOpenChat: false, isSending: true)
        panel.cardView.draftText = "Different question's draft"
        panel.cardView.card = normal
        #expect(panel.cardView.field.currentEditor() == nil)
        #expect(panel.cardView.draftText == "Different question's draft")
    }

    @Test func failureInBackgroundDoesNotActivateTheQuestionWindow() throws {
        _ = NSApplication.shared
        let question = PetQuestion(text: "Synthetic question", options: [])
        let normal = QuestionCardLayout(question, canOpenChat: false)
        let panel = QuestionFocusFixture(size: normal.size)
        defer { panel.makeFirstResponder(nil); panel.close() }
        panel.cardView.card = normal
        panel.orderFront(nil)
        try #require(panel.isVisible && panel.isKeyWindow)
        #expect(panel.makeFirstResponder(panel.cardView.field))
        panel.cardView.card = QuestionCardLayout(question, canOpenChat: false, isSending: true)
        panel.testIsKey = false
        panel.resignKey()
        panel.cardView.card = QuestionCardLayout(question, canOpenChat: false, sentNotice: "Failed")
        #expect(!panel.isKeyWindow)
        #expect(panel.cardView.field.currentEditor() == nil)
    }

    @Test func sameQuestionRefreshKeepsMarkedTextAndEditor() throws {
        _ = NSApplication.shared
        let panel = QuestionPanel()
        defer { panel.makeFirstResponder(nil); panel.close() }
        let layout = QuestionCardLayout(PetQuestion(text: "Synthetic question", options: []), canOpenChat: false)
        panel.cardView.card = layout
        panel.makeKeyAndOrderFront(nil)
        #expect(panel.makeFirstResponder(panel.cardView.field))
        let editor = try #require(panel.cardView.field.currentEditor() as? NSTextView)
        editor.setMarkedText("nihao", selectedRange: NSRange(location: 5, length: 0), replacementRange: NSRange(location: NSNotFound, length: 0))
        for _ in 0..<20 { panel.cardView.card = layout }
        #expect(panel.cardView.field.currentEditor() === editor)
        #expect(editor.hasMarkedText() && editor.string == "nihao")
    }

    @Test func controllerPreservesDraftsAcrossEscapeAndTwoChats() throws {
        _ = NSApplication.shared
        let root = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent("Resources/Assets")
        let catalog = try AnimationCatalog.load(assetsRoot: root)
        let library = try SpriteLibrary(catalog: catalog, assetsRoot: root)
        let suite = "local.yukio.question-drafts-tests." + UUID().uuidString
        let defaults = try #require(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        let controller = AppController(catalog: catalog, library: library, defaults: defaults)
        for (name, passed) in controller.questionDraftsForCheck() { #expect(passed, "\(name)") }
    }

}
