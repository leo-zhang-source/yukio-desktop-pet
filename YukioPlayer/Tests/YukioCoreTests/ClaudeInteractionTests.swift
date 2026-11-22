import Foundation
import Testing
@testable import YukioCore

@Suite struct ClaudeInteractionTests {
    private func row(_ type: String, _ seconds: Int, _ fields: [String: Any] = [:]) -> [String: Any] {
        var value: [String: Any] = ["type": type, "sessionId": "claude-interaction",
            "timestamp": ISO8601DateFormatter().string(from: Date(timeIntervalSince1970: Double(seconds)))]
        value.merge(fields) { _, new in new }; return value
    }
    private func ask(_ seconds: Int = 2, id: String = "question") -> [String: Any] {
        row("assistant", seconds, ["uuid": "request-" + id, "message": ["role": "assistant", "id": "message-" + id,
            "content": [["type": "tool_use", "name": "AskUserQuestion", "id": id,
                         "input": ["questions": [["question": "Choose a color", "options": [["label": "Red"], ["label": "Blue"]]]]]]]]])
    }
    private func start(_ parser: ClaudeTranscriptParser) {
        _ = parser.events(from: row("user", 1, ["uuid": "human", "promptId": "human", "message": ["content": "Ask me first"]]))
    }

    @Test func unrelatedResponseCannotCompleteAnUnansweredQuestion() {
        let p = ClaudeTranscriptParser(); start(p); _ = p.events(from: ask())
        _ = p.events(from: row("assistant", 3, ["uuid": "answer", "entrypoint": "sdk-cli", "message": [
            "role": "assistant", "id": "other-response", "stop_reason": "end_turn", "content": [["type": "text", "text": "Still waiting"]]]]))
        #expect(p.events(from: ["type": "last-prompt", "sessionId": "claude-interaction", "leafUuid": "answer"]).isEmpty)
    }
    @Test func desktopPlanProgressIsReadAndPlanApprovalIsWaiting() {
        let p = ClaudeTranscriptParser(); start(p)
        let events = p.events(from: row("assistant", 2, ["message": ["content": [["type": "tool_use", "id": "plan", "name": "mcp__ccd_turn__update_plan",
            "input": ["items": [["content": "First step", "status": "completed"], ["content": "Next step", "status": "in_progress"]]]]]]]))
        #expect(events.last?.kind == .todoList)
        #expect(events.last?.todos?.map(\.status) == [.completed, .inProgress])
        let approval = p.events(from: row("assistant", 3, ["message": ["content": [["type": "tool_use", "id": "review-plan", "name": "ExitPlanMode", "input": [:]]]]]))
        #expect(approval.first?.activity == .question_for_user)
    }

    @Test func parallelResultWithEarlierTimestampStillClosesItsExactQuestion() {
        let p = ClaudeTranscriptParser(); start(p); _ = p.events(from: ask())
        _ = p.events(from: row("api-request", 5, ["querySource": "sdk"]))
        let events = p.events(from: row("user", 4, ["uuid": "receipt", "message": ["content": [
            ["type": "tool_result", "tool_use_id": "question", "content": "Answered"]]]]))
        #expect(events.map(\.kind) == [.activityEnd])
        #expect(events.first?.eventID == "question")
        #expect(p.events(from: ask()).isEmpty)
    }

    @Test func duplicateHumanFrameDoesNotStartAnotherTurnOrClearWaiting() {
        let p = ClaudeTranscriptParser(); start(p); _ = p.events(from: ask())
        #expect(p.events(from: row("user", 3, ["uuid": "human", "promptId": "human", "message": ["content": "Ask me first"]])).isEmpty)
    }
    @Test(arguments: ["Permission denied by hook", "The user declined this operation in Yukio."])
    func userDenialIsNotAToolFailure(_ text: String) {
        let p = ClaudeTranscriptParser(); start(p); _ = p.events(from: ask())
        let events = p.events(from: row("user", 3, ["message": ["content": [["type": "tool_result", "tool_use_id": "question", "is_error": true, "content": text]]]]))
        #expect(events.map(\.kind) == [.activityEnd])
    }

    @Test func liveQuestionDoesNotExpireAndClientExitDoesNotMeanSuccess() {
        let router = ActivityRouter(now: 0)
        router.ingest(.init(ts: 1000, source: "claude-transcript", session: "c", kind: .activityStart,
                            eventID: "q", activity: .question_for_user, question: PetQuestion(text: "Choose")), now: 1000)
        _ = router.tick(now: 1000); _ = router.tick(now: 2000)
        router.ingest(.init(ts: 3_601_000, source: "claude-transcript", session: "c", kind: .clientState,
                            detail: "waiting", clientStateAt: 1000), now: 3_601_000)
        _ = router.tick(now: 3_601_000)
        _ = router.tick(now: 3_602_000)
        #expect(router.displayed == .question_for_user)
        router.ingest(.init(ts: 3_602_000, source: "claude-transcript", session: "c", kind: .clientState, detail: "offline"), now: 3_602_000)
        #expect(router.askingQuestion == nil)
        #expect(router.sessions["c"]?.taskActive == false)
        #expect(router.sessions["c"]?.finalAnswerAt == nil)
    }

    @Test func bridgeReceiptAfterTerminalProofDoesNotLoseCompletion() {
        let router = ActivityRouter(now: 0)
        router.ingest(.init(ts: 1000, source: "claude-transcript", session: "c", kind: .taskStart), now: 1000)
        router.ingest(.init(ts: 2000, source: "claude-transcript", session: "c", kind: .activityStart,
                            eventID: "bridge-q", activity: .question_for_user, question: PetQuestion(text: "Choose"), relatedCallID: "raw-q"), now: 2100)
        router.ingest(.init(ts: 3000, source: "claude-transcript", session: "c", kind: .finalAnswer), now: 3000)
        router.ingest(.init(ts: 3000, source: "claude-transcript", session: "c", kind: .taskEnd), now: 3000)
        #expect(router.sessions["c"]?.taskActive == true)
        router.ingest(.init(ts: 3100, source: "claude-transcript", session: "c", kind: .activityEnd, eventID: "bridge-q"), now: 3100)
        #expect(router.sessions["c"]?.taskActive == false)
        #expect(router.sessions["c"]?.finalAnswerAt == 3000)
    }

    @Test func transcriptReceiptRetiresEveryBridgeItemOnlyForItsCall() {
        let router = ActivityRouter(now: 0)
        for (id, raw) in [("part-1", "q"), ("part-2", "q"), ("other", "other-q")] {
            router.ingest(.init(ts: 1000, source: "claude-transcript", session: "c", kind: .activityStart,
                                eventID: id, activity: .question_for_user, question: PetQuestion(text: id), relatedCallID: raw), now: 1000)
        }
        router.ingest(.init(ts: 2000, source: "claude-transcript", session: "c", kind: .activityEnd, eventID: "q"), now: 2000)
        #expect(router.sessions["c"]?.open.map(\.id) == ["other"])
    }

    @Test func processRegistryRecoversOldWaitAndRejectsReusedPID() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let projects = root.appendingPathComponent("projects/p")
        let registry = root.appendingPathComponent("sessions")
        try FileManager.default.createDirectory(at: projects, withIntermediateDirectories: true)
        try FileManager.default.createDirectory(at: registry, withIntermediateDirectories: true)
        let sid = UUID().uuidString
        let stamp = Date().timeIntervalSince1970 * 1000
        var human = row("user", Int(stamp / 1000) - 3600, ["message": ["content": "Ask first"]])
        var question = ask(Int(stamp / 1000) - 3599)
        human["sessionId"] = sid; question["sessionId"] = sid
        let file = projects.appendingPathComponent(sid + ".jsonl")
        var data = try JSONSerialization.data(withJSONObject: human); data.append(10)
        data.append(try JSONSerialization.data(withJSONObject: question)); data.append(10)
        try data.write(to: file)
        try FileManager.default.setAttributes([.modificationDate: Date(timeIntervalSince1970: stamp / 1000 - 3600)], ofItemAtPath: file.path)
        let metadata: [String: Any] = ["pid": 123, "sessionId": sid, "status": "waiting", "pidDomain": "darwin",
                                       "procStart": "test-start", "updatedAt": stamp - 3_598_000]
        try JSONSerialization.data(withJSONObject: metadata).write(to: registry.appendingPathComponent("123.json"))
        var alive = true
        let runtime = ClaudeRuntimeIndex(root: registry, matchesProcess: { pid, start in alive && pid == 123 && start == "test-start" })
        let source = ClaudeTranscriptSource(projectsDir: root.appendingPathComponent("projects"), runtimeIndex: runtime)
        let router = ActivityRouter(now: stamp)
        for event in source.poll(now: stamp) { router.ingest(event, now: min(stamp, event.ts)) }
        #expect(router.sessions[sid]?.open.contains { $0.state == .question_for_user } == true)
        #expect(router.isLive(router.sessions[sid]!, now: stamp))
        alive = false
        let ended = source.poll(now: stamp + 2500)
        #expect(ended.contains { $0.kind == .clientState && $0.detail == "offline" })
        for event in ended { router.ingest(event, now: stamp + 2500) }
        #expect(router.sessions[sid]?.taskActive == false)
    }

    @Test func desktopRewindRetiresOnlyExplicitUnambiguousPriorSession() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let folder = root.appendingPathComponent("account/org")
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        let old = UUID().uuidString, current = UUID().uuidString, owner = "local_" + UUID().uuidString
        let path = folder.appendingPathComponent(owner + ".json")
        try JSONSerialization.data(withJSONObject: ["sessionId": owner, "cliSessionId": current, "priorCliSessionIds": [old]]).write(to: path)
        let links = ClaudeSessionLinks(sessionsDir: root)
        #expect(links.retiredTranscriptSessions() == [old])
        let other = "local_" + UUID().uuidString
        try JSONSerialization.data(withJSONObject: ["sessionId": other, "cliSessionId": old]).write(to: folder.appendingPathComponent(other + ".json"))
        #expect(links.retiredTranscriptSessions().isEmpty)
    }
}
