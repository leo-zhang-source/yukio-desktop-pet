import AppKit
import Testing
import YukioCore
@testable import YukioPlayer

@Suite @MainActor struct QuestionDraftTests {
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
}
