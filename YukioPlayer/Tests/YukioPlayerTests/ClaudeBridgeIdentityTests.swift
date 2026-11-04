import Foundation
import Testing
import YukioCore
@testable import YukioPlayer

@Suite struct ClaudeBridgeIdentityTests {
    let first = PetQuestion(header: "Choice", text: "Which?", options: [.init(label: "A"), .init(label: "B")])
    let second = PetQuestion(text: "Another?", options: [.init(label: "C"), .init(label: "D")])

    func fixture(_ root: URL, session: String = "s", callID: String = "toolu_same", provider: String? = nil,
                 questions: [PetQuestion]? = nil, expires: Double = 60_000, done: Bool = false) throws -> URL {
        let now = Date().timeIntervalSince1970 * 1000
        let request = ClaudeQuestionBridge.Request(provider: provider, id: UUID().uuidString, session: session,
            callID: callID, questions: questions ?? [first], pid: getpid(), createdAt: now, expiresAt: now + expires)
        let dir = root.appendingPathComponent(request.id)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        try JSONEncoder().encode(request).write(to: dir.appendingPathComponent("request.json"))
        if done { try Data().write(to: dir.appendingPathComponent("done")) }
        return dir
    }

    @Test func rawToolIDAnswersTwoConsecutiveHooksAndMultipleQuestions() async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let bridge = ClaudeQuestionBridge(root: root)
        // Repeating question text in a later turn must still use that turn's ID.
        for callID in ["toolu_round1", "toolu_round2"] {
            _ = bridge.poll(now: Date().timeIntervalSince1970 * 1000)
            let raw: [[String: Any]] = [["header": "Choice", "question": "Which?", "options": ["A", "B"]],
                                      ["question": "Another?", "options": ["C", "D"]]]
            let input = try JSONSerialization.data(withJSONObject: ["hook_event_name": "PreToolUse", "tool_name": "AskUserQuestion",
                "session_id": "s", "tool_use_id": callID, "tool_input": ["questions": raw]])
            let hook = Task.detached { ClaudeQuestionBridge.runHook(input: input, root: root, waitSeconds: 8) }
            var event: PetEvent?
            for _ in 0..<100 {
                event = bridge.poll(now: Date().timeIntervalSince1970 * 1000).first { $0.question == first }
                if event != nil { break }
                try await Task.sleep(nanoseconds: 25_000_000)
            }
            _ = try #require(event)
            // Answer in reverse order to prove the full question selects its index.
            try bridge.send(session: "s", callID: callID, answer: callID + " D", question: second)
            try bridge.send(session: "s", callID: callID, answer: callID + " A", question: first)
            let output = try #require(JSONSerialization.jsonObject(with: await hook.value) as? [String: Any])
            let specific = try #require(output["hookSpecificOutput"] as? [String: Any])
            let updated = try #require(specific["updatedInput"] as? [String: Any])
            #expect(updated["answers"] as? [String: String] == ["Which?": callID + " A", "Another?": callID + " D"])
            _ = bridge.poll(now: Date().timeIntervalSince1970 * 1000)
        }
    }

    @Test func sameCallIDInOtherSessionsAndProvidersCannotReceiveAnswer() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let a = try fixture(root), b = try fixture(root, session: "other"), d = try fixture(root, provider: "deepseek")
        try JSONEncoder().encode("A").write(to: a.appendingPathComponent("receipt-0.json"))
        let bridge = ClaudeQuestionBridge(root: root)
        try bridge.send(session: "s", callID: "toolu_same", answer: "A", question: first)
        for (session, callID, question) in [("wrong", "toolu_same", first), ("s", "wrong", first), ("s", "toolu_same", second)] {
            #expect(throws: ClaudeQuestionBridge.Failure.notConnected) {
                try bridge.send(session: session, callID: callID, answer: "A", question: question)
            }
        }
        #expect(throws: ClaudeQuestionBridge.Failure.notConnected) {
            try bridge.send(session: "s", callID: "toolu_same", answer: "A", provider: "deepseek", question: first)
        }
        for dir in [a, b, d] { #expect(!FileManager.default.fileExists(atPath: dir.appendingPathComponent("answer-0.json").path)) }
    }

    @Test func ambiguousRequestsAndQuestionIndicesAreRejected() throws {
        for duplicate in [false, true] {
            let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
            defer { try? FileManager.default.removeItem(at: root) }
            let a = try fixture(root, questions: duplicate ? [first, first] : [first])
            if !duplicate { _ = try fixture(root) }
            #expect(throws: ClaudeQuestionBridge.Failure.ambiguous) {
                try ClaudeQuestionBridge(root: root).send(session: "s", callID: "toolu_same", answer: "A", question: first)
            }
            #expect(!FileManager.default.fileExists(atPath: a.appendingPathComponent("answer-0.json").path))
        }
    }

    @Test func inactiveRequestsAndRawApprovalsAreRejected() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let expired = try fixture(root, expires: -1), done = try fixture(root, done: true)
        let approval = ApprovalQuestion.make(provider: "Claude", details: "Synthetic test")
        let permission = try fixture(root, callID: "permission", questions: [approval])
        let bridge = ClaudeQuestionBridge(root: root)
        #expect(throws: ClaudeQuestionBridge.Failure.notConnected) {
            try bridge.send(session: "s", callID: "toolu_same", answer: "A", question: first)
        }
        #expect(throws: ClaudeQuestionBridge.Failure.notConnected) {
            try bridge.send(session: "s", callID: "permission", answer: ApprovalQuestion.allow, question: approval)
        }
        for dir in [expired, done, permission] { #expect(!FileManager.default.fileExists(atPath: dir.appendingPathComponent("answer-0.json").path)) }
    }

    @Test func receiptRetryCannotOverwriteOrChangeTheQuestion() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let dir = try fixture(root, done: true)
        let receipt = dir.appendingPathComponent("receipt-0.json"), data = try JSONEncoder().encode("A")
        try data.write(to: receipt)
        let bridge = ClaudeQuestionBridge(root: root)
        try bridge.send(session: "s", callID: "toolu_same", answer: "A", question: first)
        #expect(throws: ClaudeQuestionBridge.Failure.expired) {
            try bridge.send(session: "s", callID: "toolu_same", answer: "B", question: first)
        }
        #expect(throws: ClaudeQuestionBridge.Failure.expired) {
            try bridge.send(session: "s", callID: "yukio-claude:\(dir.lastPathComponent):0", answer: "A", question: second)
        }
        #expect(try Data(contentsOf: receipt) == data)
        #expect(!FileManager.default.fileExists(atPath: dir.appendingPathComponent("answer-0.json").path))
    }

    @Test func inFlightAnswerIsNeverReplaced() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let dir = try fixture(root), answer = dir.appendingPathComponent("answer-0.json"), data = try JSONEncoder().encode("A")
        try data.write(to: answer)
        #expect(throws: ClaudeQuestionBridge.Failure.unconfirmed) {
            try ClaudeQuestionBridge(root: root).send(session: "s", callID: "toolu_same", answer: "B", question: first)
        }
        #expect(try Data(contentsOf: answer) == data)
    }
}
