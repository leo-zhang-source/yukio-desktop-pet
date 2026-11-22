import AppKit
import Testing
import YukioCore
@testable import YukioPlayer

@Suite struct BackgroundAnswersTests {
    let q = PetQuestion(text: "Which?", options: [.init(label: "A"), .init(label: "B")])
    @Test func helperRefreshOnlyRecognizesTheConfiguredOwnedCommand() {
        let path = "/Users/test/Library/Application Support/YukioPlayer/YukioAnswerBridge"
        let configured = BackgroundAnswerSetup.mergedSettings(["model": "user-choice"], executable: path)
        #expect(BackgroundAnswerSetup.hasManagedClaudeHook(configured, helper: path))
        #expect(!BackgroundAnswerSetup.hasManagedClaudeHook(configured, helper: path + "-other"))
        #expect(!BackgroundAnswerSetup.hasManagedClaudeHook([:], helper: path))
        #expect(!BackgroundAnswerSetup.hasManagedClaudeHook(["hooks": ["PreToolUse": [["hooks": [["type": "command", "command": "echo YukioAnswerBridge"]]]]]], helper: path))
    }
    func snapshot() -> [String: Any] {
        ["id": "session", "cwd": "/tmp", "turns": [["status": "inProgress", "items": [
            ["id": "call", "type": "agentMessage", "questions": [["title": "Which?", "options": ["A", "B"]]]]
        ]]]]
    }
    @Test func codexOnlyFollowingDoesNotAdvertiseOtherProviders() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        _ = ClaudeQuestionBridge(root: root).poll(now: Date().timeIntervalSince1970 * 1000, providers: ["gpt"])
        #expect(!FileManager.default.fileExists(atPath: root.appendingPathComponent("listener-deepseek").path))
        #expect(!FileManager.default.fileExists(atPath: root.appendingPathComponent("listener").path))
    }
    @Test func exactThreadAndQuestionRequired() throws {
        #expect(throws: (any Error).self) { try CodexAnswerClient.submission(snapshot: snapshot(), session: "other", callID: "call", question: q, answer: "A") }
        #expect(throws: (any Error).self) { try CodexAnswerClient.submission(snapshot: snapshot(), session: "session", callID: "other", question: q, answer: "A") }
        #expect(throws: (any Error).self) { try CodexAnswerClient.submission(snapshot: snapshot(), session: "session", callID: "call", question: .init(text: "Unrelated"), answer: "A") }
    }
    @Test func acceptedAsyncReplyUsesStructuredQuestionID() throws {
        let s = try CodexAnswerClient.submission(snapshot: snapshot(), session: "session", callID: "call", question: q, answer: "中文 <answer>")
        #expect(s.method == "thread-follower-steer-turn")
        let content = try #require(s.params["input"] as? [[String: Any]])
        let text = try #require(content[0]["text"] as? String)
        #expect(text.contains("中文 <answer>"))
        var snap = snapshot()
        var turns = snap["turns"] as! [[String: Any]]
        var items = turns[0]["items"] as! [[String: Any]]
        items.append(["type": "steeringUserMessage", "status": "accepted", "content": content])
        turns[0]["items"] = items; snap["turns"] = turns
        #expect(throws: (any Error).self) { try CodexAnswerClient.submission(snapshot: snap, session: "session", callID: "call", question: q, answer: "A") }
    }
    @Test func asyncQuestionRepliesAreIndexedAndCheckedAcrossTurns() throws {
        var snap = snapshot()
        var original = (snap["turns"] as! [[String: Any]])[0]
        original["status"] = "completed"
        original["items"] = [["id": "call", "type": "agentMessage", "questions": [
            ["title": "Which?", "options": ["A", "B"]], ["title": "Second?", "options": ["X", "Y"]]]]]
        snap["turns"] = [original]
        let second = PetQuestion(text: "Second?", options: [.init(label: "X"), .init(label: "Y")])
        let firstReply = try CodexAnswerClient.submission(snapshot: snap, session: "session", callID: "call", question: q, answer: "A")
        #expect(firstReply.method == "thread-follower-start-turn")
        let turnStart = try #require(firstReply.params["turnStart"] as? [String: Any])
        let request = try #require(turnStart["request"] as? [String: Any])
        snap["turns"] = [original, ["status": "inProgress", "items": [["type": "userMessage", "content": request["input"]!]]]]
        #expect(throws: CodexAnswerClient.Failure.expired) {
            try CodexAnswerClient.submission(snapshot: snap, session: "session", callID: "call", question: q, answer: "B")
        }
        let next = try CodexAnswerClient.submission(snapshot: snap, session: "session", callID: "call", question: second, answer: "Y", questionIndex: 1)
        #expect(next.method == "thread-follower-steer-turn")
        let input = try #require(next.params["input"] as? [[String: Any]])
        #expect((input[0]["text"] as? String)?.contains("Second?") == true)
        #expect(throws: CodexAnswerClient.Failure.expired) {
            try CodexAnswerClient.submission(snapshot: snap, session: "session", callID: "call", question: q, answer: "A", questionIndex: 1)
        }
    }
    @Test func blockingQuestionsUseRequestResponseNotChat() throws {
        var snap = snapshot()
        snap["requests"] = [["id": 42, "method": "item/tool/requestUserInput", "params": ["itemId": "blocking", "questions": [["id": "choice", "question": "Which?"]]]]]
        let s = try CodexAnswerClient.submission(snapshot: snap, session: "session", callID: "blocking", question: q, answer: "B")
        #expect(s.method == "thread-follower-submit-user-input")
        #expect(s.params["requestId"] as? Int == 42)
        #expect(s.params["input"] == nil)
        snap["requests"] = [["id": 42, "method": "item/tool/requestUserInput", "params": ["itemId": "blocking", "questions": [
            ["id": "choice", "question": "Which?"], ["id": "second", "question": "Second?"]]]]]
        #expect(throws: CodexAnswerClient.Failure.ambiguous) {
            try CodexAnswerClient.submission(snapshot: snap, session: "session", callID: "blocking", question: q, answer: "B")
        }
    }
    func canonicalSnapshot(_ legacy: [String: Any]) -> [String: Any] {
        var result = legacy
        let turns = legacy["turns"] as! [[String: Any]]
        result["turns"] = [] as [[String: Any]]
        result["turnHistory"] = ["kind": "canonical", "history": [
            "entitiesByKey": Dictionary(uniqueKeysWithValues: turns.enumerated().map { ("turn-\($0.offset)", $0.element) }),
            "islands": [["entries": turns.indices.map { ["key": "index-\($0)", "value": "turn-\($0)"] }]]
        ]]
        return result
    }
    @Test func canonicalHistoryAnswersLiveQuestionWithEmptyLegacyTurns() throws {
        let s = try CodexAnswerClient.submission(snapshot: canonicalSnapshot(snapshot()), session: "session", callID: "call", question: q, answer: "A")
        #expect(s.method == "thread-follower-steer-turn")
        // Duplicate protection must also read the canonical history.
        var legacy = snapshot()
        var turn = (legacy["turns"] as! [[String: Any]])[0]
        var items = turn["items"] as! [[String: Any]]
        items.append(["type": "steeringUserMessage", "status": "accepted", "content": s.params["input"]!])
        turn["items"] = items; legacy["turns"] = [turn]
        #expect(throws: CodexAnswerClient.Failure.expired) {
            try CodexAnswerClient.submission(snapshot: canonicalSnapshot(legacy), session: "session", callID: "call", question: q, answer: "B")
        }
    }
    @Test func canonicalHistoryDoesNotUseStaleLegacyOrDetachedTurns() throws {
        var snap = snapshot()
        snap["turnHistory"] = ["kind": "canonical", "history": [
            "entitiesByKey": ["detached": (snap["turns"] as! [[String: Any]])[0]],
            "islands": [["entries": [] as [[String: Any]]]]
        ]]
        #expect(throws: CodexAnswerClient.Failure.expired) {
            try CodexAnswerClient.submission(snapshot: snap, session: "session", callID: "call", question: q, answer: "A")
        }
        snap["turnHistory"] = ["kind": "canonical", "history": [
            "entitiesByKey": [:] as [String: [String: Any]],
            "islands": [["entries": [["key": "index", "value": "missing"]]]]
        ]]
        #expect(throws: CodexAnswerClient.Failure.protocolMismatch) {
            try CodexAnswerClient.submission(snapshot: snap, session: "session", callID: "call", question: q, answer: "A")
        }
    }
    @Test func onlyOneCompleteCurrentIslandCoversAnAsyncQuestion() {
        var snap = canonicalSnapshot(snapshot())
        var history = (snap["turnHistory"] as! [String: Any])["history"] as! [String: Any]
        var island = (history["islands"] as! [[String: Any]])[0]
        #expect(!CodexAnswerClient.tailCoversQuestion(snap, callID: "call"))
        island["newerBoundary"] = ["status": "exhausted"]
        island["olderBoundary"] = ["status": "available"]
        history["islands"] = [island]; snap["turnHistory"] = ["kind": "canonical", "history": history]
        #expect(CodexAnswerClient.tailCoversQuestion(snap, callID: "call"))
        #expect(!CodexAnswerClient.tailCoversQuestion(snap, callID: "missing"))
        history["islands"] = [island, island]; snap["turnHistory"] = ["kind": "canonical", "history": history]
        #expect(!CodexAnswerClient.tailCoversQuestion(snap, callID: "call"))
    }
    @Test func canonicalHistorySupportsBlockingReceiptLookup() throws {
        let receipt: [String: Any] = ["requestId": 42, "completed": true]
        let snap = canonicalSnapshot(["turns": [["status": "completed", "items": [receipt]]]])
        let turns = try CodexAnswerClient.turns(in: snap)
        let items = try #require(turns.first?["items"] as? [[String: Any]])
        #expect(items.first?["requestId"] as? Int == 42)
        #expect(items.first?["completed"] as? Bool == true)
    }
    @Test func claudeHookPreservesOtherSettingsAndIsIdempotent() throws {
        let original: [String: Any] = ["model": "unchanged", "permissions": ["deny": ["Bash"]], "hooks": ["PreToolUse": [["matcher": "*", "hooks": [["type": "command", "command": "existing"]]]]]]
        let once = BackgroundAnswerSetup.mergedSettings(original, executable: "/tmp/YukioAnswerBridge")
        let twice = BackgroundAnswerSetup.mergedSettings(once, executable: "/tmp/YukioAnswerBridge")
        #expect(try JSONSerialization.data(withJSONObject: once, options: .sortedKeys) == JSONSerialization.data(withJSONObject: twice, options: .sortedKeys))
        #expect(twice["model"] as? String == "unchanged")
        #expect((twice["permissions"] as? [String: [String]])?["deny"] == ["Bash"])
    }
    @Test(arguments: ["PreToolUse", "PermissionRequest"]) func claudeTwoQuestionRoundTripAndNoListenerFallback(hookEvent: String) async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let bridge = ClaudeQuestionBridge(root: root)
        let input: [String: Any] = ["hook_event_name": hookEvent, "tool_name": "AskUserQuestion", "session_id": "s", "tool_use_id": "c", "tool_input": ["questions": [["question": "One?", "options": ["A", "B"]], ["question": "Two?", "options": ["C", "D"]]]]]
        let bytes = try JSONSerialization.data(withJSONObject: input)
        #expect(ClaudeQuestionBridge.runHook(input: bytes, root: root, waitSeconds: 2) == Data("{}".utf8))
        _ = bridge.poll(now: Date().timeIntervalSince1970 * 1000)
        let hook = Task.detached { ClaudeQuestionBridge.runHook(input: bytes, root: root, waitSeconds: 5) }
        for expected in ["One?", "Two?"] {
            var pending: PetEvent?
            for _ in 0..<80 {
                pending = bridge.poll(now: Date().timeIntervalSince1970 * 1000).first { $0.question?.text == expected }
                if pending != nil { break }
                try await Task.sleep(nanoseconds: 25_000_000)
            }
            let event = try #require(pending)
            #expect(event.question?.isApproval == false)
            try bridge.send(session: "s", callID: try #require(event.eventID), answer: "回答 " + expected)
        }
        let output = try #require(JSONSerialization.jsonObject(with: await hook.value) as? [String: Any])
        let specific = try #require(output["hookSpecificOutput"] as? [String: Any])
        let decision = hookEvent == "PermissionRequest" ? try #require(specific["decision"] as? [String: Any]) : specific
        #expect(decision[hookEvent == "PermissionRequest" ? "behavior" : "permissionDecision"] as? String == "allow")
        let updated = try #require(decision["updatedInput"] as? [String: Any])
        #expect(updated["answers"] as? [String: String] == ["One?": "回答 One?", "Two?": "回答 Two?"])
    }
    @Test(arguments: ["Bash", "ExitPlanMode"], [true, false])
    func claudePermissionDecisionsPreserveInputAndNeverCreatePermanentRules(tool: String, allowed: Bool) async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let bridge = ClaudeQuestionBridge(root: root)
        _ = bridge.poll(now: Date().timeIntervalSince1970 * 1000)
        let input = ["command": "true", "plan": "Only inspect the test folder"]
        let bytes = try JSONSerialization.data(withJSONObject: ["hook_event_name": "PermissionRequest", "tool_name": tool,
            "session_id": "permission-session", "tool_input": input])
        let hook = Task.detached { ClaudeQuestionBridge.runHook(input: bytes, root: root, waitSeconds: 5) }
        var pending: PetEvent?
        for _ in 0..<80 {
            pending = bridge.poll(now: Date().timeIntervalSince1970 * 1000).first { $0.question != nil }
            if pending != nil { break }
            try await Task.sleep(nanoseconds: 25_000_000)
        }
        let event = try #require(pending)
        #expect(event.question?.isApproval == true)
        try bridge.send(session: "permission-session", callID: try #require(event.eventID), answer: allowed ? ApprovalQuestion.allow : ApprovalQuestion.deny)
        let result = try #require(JSONSerialization.jsonObject(with: await hook.value) as? [String: Any])
        let specific = try #require(result["hookSpecificOutput"] as? [String: Any])
        let decision = try #require(specific["decision"] as? [String: Any])
        #expect(decision["behavior"] as? String == (allowed ? "allow" : "deny"))
        #expect(decision["updatedPermissions"] == nil)
        if allowed { #expect(decision["updatedInput"] as? [String: String] == input) }
        else { #expect(decision["updatedInput"] == nil) }
    }
    @Test func permissionHookCorrelationRequiresOneUnresolvedExactCall() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let file = root.appendingPathComponent("transcript.jsonl")
        let input: [String: Any] = ["questions": [["question": "Choose", "options": ["A", "B"]]]]
        let hook: [String: Any] = ["session_id": "s", "tool_name": "AskUserQuestion", "tool_input": input, "transcript_path": file.path]
        func call(_ id: String) -> [String: Any] {
            ["type": "assistant", "sessionId": "s", "message": ["content": [["type": "tool_use", "name": "AskUserQuestion", "id": id, "input": input]]]]
        }
        func write(_ rows: [[String: Any]]) throws {
            var data = Data()
            for row in rows { data.append(try JSONSerialization.data(withJSONObject: row)); data.append(10) }
            try data.write(to: file)
        }
        try write([call("first")])
        #expect(ClaudeQuestionBridge.transcriptCallID(hook) == "first")
        try write([call("first"), call("second")])
        #expect(ClaudeQuestionBridge.transcriptCallID(hook) == nil)
        try write([call("first"), ["type": "user", "sessionId": "s", "message": ["content": [["type": "tool_result", "tool_use_id": "first"]]]]])
        #expect(ClaudeQuestionBridge.transcriptCallID(hook) == nil)
        try write([call("first"), ["type": "user", "sessionId": "s", "message": ["content": "A new request"]]])
        #expect(ClaudeQuestionBridge.transcriptCallID(hook) == nil)
    }
    @Test func completeReceiptsRetireTranscriptCopyAndPartialAnswersSurviveSameCallHandoff() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let id = UUID().uuidString, dir = root.appendingPathComponent(id)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let now = Date().timeIntervalSince1970 * 1000
        let request = ClaudeQuestionBridge.Request(id: id, session: "s", callID: "raw", questions: [q, .init(text: "Second?")],
                                                   pid: getpid(), createdAt: now - 1000, expiresAt: now + 10000)
        try JSONEncoder().encode(request).write(to: dir.appendingPathComponent("request.json"))
        let bridge = ClaudeQuestionBridge(root: root)
        #expect(bridge.poll(now: now).first?.question == q)
        try JSONEncoder().encode("中文回答").write(to: dir.appendingPathComponent("receipt-0.json"))
        let next = bridge.poll(now: now + 1)
        #expect(next.first?.question?.text == "Second?")
        #expect(!next.contains { $0.kind == .activityEnd && $0.eventID == "raw" })
        let resumed = ClaudeQuestionBridge.Request(id: UUID().uuidString, session: "s", callID: "raw", questions: request.questions,
                                                   pid: getpid(), createdAt: now + 2, expiresAt: now + 10000)
        #expect(ClaudeQuestionBridge.priorAnswers(root: root, request: resumed).keys.sorted() == [0])
        let foreign = ClaudeQuestionBridge.Request(id: UUID().uuidString, session: "other", callID: "raw", questions: request.questions,
                                                   pid: getpid(), createdAt: now + 2, expiresAt: now + 10000)
        #expect(ClaudeQuestionBridge.priorAnswers(root: root, request: foreign).isEmpty)
        try JSONEncoder().encode("second answer").write(to: dir.appendingPathComponent("receipt-1.json"))
        #expect(bridge.poll(now: now + 3).contains { $0.kind == .activityEnd && $0.eventID == "raw" && $0.relatedCallID == "raw" })
    }
    @Test @MainActor func failureNoticeKeepsClickableOptions() {
        let card = QuestionCardLayout(q, sentNotice: "Connection failed")
        let rect = NSRect(origin: .zero, size: card.size)
        #expect(QuestionCardLayout.probePoints(card, in: rect).contains { card.hit(at: $0.1, in: rect) == .option(0) })
        let busy = QuestionCardLayout(q, sentNotice: "Sending", isSending: true)
        #expect(!QuestionCardLayout.probePoints(busy, in: NSRect(origin: .zero, size: busy.size)).contains { busy.hit(at: $0.1, in: NSRect(origin: .zero, size: busy.size)) == .option(0) })
    }
}
