import AppKit
import Testing
import YukioCore
@testable import YukioPlayer

@Suite @MainActor struct QuestionDraftTests {
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
