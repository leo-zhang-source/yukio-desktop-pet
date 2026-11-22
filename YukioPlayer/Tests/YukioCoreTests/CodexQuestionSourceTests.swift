import Foundation
import Testing
@testable import YukioCore

@Suite struct CodexQuestionSourceTests {
    @Test func restoreBeyondTailAndReplaceOnlyOneSource() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let file = root.appendingPathComponent("rollout-file-a.jsonl"), other = root.appendingPathComponent("rollout-file-b.jsonl")
        let t = Date().timeIntervalSince1970 * 1000
        func json(_ value: Any) throws -> String {
            String(data: try JSONSerialization.data(withJSONObject: value), encoding: .utf8)!
        }
        func row(_ kind: String, _ payload: [String: Any]) throws -> String {
            var value = payload; value["type"] = kind
            return try json(["type": "response_item", "timestamp": ISO8601DateFormatter().string(from: Date(timeIntervalSince1970: t/1000-60)), "payload": value]) + "\n"
        }
        func header(_ id: String) throws -> String { try json(["type": "session_meta", "payload": ["id": id]]) + "\n" }
        func append(_ value: String) throws {
            let handle = try FileHandle(forWritingTo: file)
            defer { try? handle.close() }
            try handle.seekToEnd(); try handle.write(contentsOf: Data(value.utf8))
        }
        let question = try row("function_call", ["name": "request_user_input_async", "call_id": "q", "arguments": ["questions": [["title": "First?"], ["title": "Second?"]]]])
        let noise = String(repeating: try row("token_count", ["padding": String(repeating: "x", count: 4096)]), count: 600)
        try (header("chat-a") + question + noise + row("task_complete", ["last_agent_message": "Finished this turn"])).write(to: file, atomically: true, encoding: .utf8)
        try (header("chat-b") + question).write(to: other, atomically: true, encoding: .utf8)
        let source = CodexSessionsSource(sessionsDir: root), router = ActivityRouter(now: t)
        for index in 0..<8 {
            for event in source.poll(now: t + Double(index)) { router.ingest(event, now: t + Double(index)) }
        }
        #expect(router.pinSession("chat-a", now: t + 9))
        router.settle(now: t + 9)
        #expect(router.askingQuestion?.question.text == "First?")
        let reply = "<send_user_message_question_reply>" + (try json([["questionItemId": json(["request_user_input_async", "q", 0]), "answer": "A"]])) + "</send_user_message_question_reply>"
        try append(row("message", ["role": "user", "content": reply]))
        for event in source.poll(now: t + 10) { router.ingest(event, now: t + 10) }
        #expect(router.askingQuestion?.question.text == "Second?")
        try Data(header("chat-a").utf8).write(to: file, options: .atomic)
        for event in source.poll(now: t + 11) { router.ingest(event, now: t + 11) }
        #expect(router.askingQuestion == nil)
        #expect(router.pinSession("chat-b", now: t + 12))
        router.settle(now: t + 12)
        #expect(router.askingQuestion?.question.text == "First?")
        let fragment = root.appendingPathComponent("rollout-b-part.jsonl")
        try Data(header("chat-b").utf8).write(to: fragment)
        for event in source.poll(now: t + 3000) { router.ingest(event, now: t + 3000) }
        try FileManager.default.removeItem(at: fragment)
        for event in source.poll(now: t + 3001) { router.ingest(event, now: t + 3001) }
        #expect(router.askingQuestion?.question.text == "First?")
    }
}
