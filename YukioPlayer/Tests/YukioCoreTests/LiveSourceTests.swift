import Foundation
import Testing
@testable import YukioCore

@Suite(.serialized) struct LiveSourceTests {
    let root: URL
    let project: URL

    init() throws {
        root = FileManager.default.temporaryDirectory.appendingPathComponent("yukio-test-\(UUID().uuidString)")
        project = root.appendingPathComponent("projects/-Users-me-app")
        try FileManager.default.createDirectory(at: project, withIntermediateDirectories: true)
    }

    func now() -> Double { Date().timeIntervalSince1970 * 1000 }

    func stamp(_ ms: Double) -> String {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f.string(from: Date(timeIntervalSince1970: ms / 1000))
    }

    func userLine(_ session: String, _ ms: Double) -> String {
        #"{"type":"user","sessionId":"\#(session)","timestamp":"\#(stamp(ms))","message":{"role":"user","content":"go"}}"# + "\n"
    }

    func toolLine(_ session: String, _ ms: Double, id: String, command: String) -> String {
        #"{"type":"assistant","sessionId":"\#(session)","timestamp":"\#(stamp(ms))","message":{"stop_reason":"tool_use","content":[{"type":"tool_use","id":"\#(id)","name":"Bash","input":{"command":"\#(command)"}}]}}"# + "\n"
    }

    func append(_ url: URL, _ s: String) throws {
        if !FileManager.default.fileExists(atPath: url.path) {
            FileManager.default.createFile(atPath: url.path, contents: nil)
        }
        let h = try FileHandle(forWritingTo: url)
        try h.seekToEnd()
        try h.write(contentsOf: Data(s.utf8))
        try h.close()
    }

    @Test func bootstrapsRecentSessionAndTailsNewLines() throws {
        let file = project.appendingPathComponent("S1.jsonl")
        let t0 = now()
        try append(file, userLine("S1", t0 - 5000))
        let source = ClaudeTranscriptSource(projectsDir: root.appendingPathComponent("projects"))

        let boot = source.poll(now: t0)
        #expect(boot.map(\.kind) == [.taskStart])
        #expect(source.status.directoryFound && source.status.trackedFiles == 1)

        // 追加半行：不应产生事件；补完后产生一次。
        let line = toolLine("S1", t0, id: "tu1", command: "swift test")
        let cut = line.index(line.startIndex, offsetBy: 40)
        try append(file, String(line[..<cut]))
        #expect(source.poll(now: t0 + 250).isEmpty)
        try append(file, String(line[cut...]))
        let live = source.poll(now: t0 + 500)
        #expect(live.count == 1 && live[0].activity == .verify && live[0].eventID == "tu1")
    }

    @Test func oldSessionsAreNotReplayedAsLive() throws {
        let file = project.appendingPathComponent("OLD.jsonl")
        let t0 = now()
        try append(file, userLine("OLD", t0 - 3_600_000))
        try FileManager.default.setAttributes([.modificationDate: Date(timeIntervalSinceNow: -3600)], ofItemAtPath: file.path)
        let source = ClaudeTranscriptSource(projectsDir: root.appendingPathComponent("projects"))
        #expect(source.poll(now: t0).isEmpty)
        // 旧会话之后被继续使用：只产生新写入的事件。
        try append(file, toolLine("OLD", t0 + 100, id: "x", command: "ls"))
        let evs = source.poll(now: t0 + 300)
        #expect(evs.map(\.kind) == [.activityStart] && evs[0].activity == .read_file)
    }

    @Test func newSessionCreatedAfterStartupIsDiscovered() throws {
        let source = ClaudeTranscriptSource(projectsDir: root.appendingPathComponent("projects"))
        let t0 = now()
        #expect(source.poll(now: t0).isEmpty)
        try append(project.appendingPathComponent("NEW.jsonl"), userLine("NEW", t0 + 10))
        #expect(source.poll(now: t0 + 500).isEmpty)          // 尚未到重新扫描时间
        let evs = source.poll(now: t0 + 2500)
        #expect(evs.map(\.kind) == [.taskStart] && evs[0].session == "NEW")
    }

    @Test func deletedSessionFileAbortsThatSession() throws {
        let file = project.appendingPathComponent("GONE.jsonl")
        let t0 = now()
        try append(file, userLine("GONE", t0))
        let source = ClaudeTranscriptSource(projectsDir: root.appendingPathComponent("projects"))
        _ = source.poll(now: t0)
        try FileManager.default.removeItem(at: file)
        let evs = source.poll(now: t0 + 300)
        #expect(evs.map(\.kind) == [.taskAbort] && evs[0].session == "GONE")
    }

    @Test func missingDirectoryIsReported() {
        let source = ClaudeTranscriptSource(projectsDir: root.appendingPathComponent("nope"))
        #expect(source.poll(now: now()).isEmpty)
        #expect(source.status.directoryFound == false)
    }

    private func jsonLine(_ row: [String: Any]) throws -> String {
        String(data: try JSONSerialization.data(withJSONObject: row), encoding: .utf8)! + "\n"
    }

    private func completionRows(_ t: Double) -> [[String: Any]] {
        [
            ["type": "user", "sessionId": "S", "timestamp": stamp(t), "promptId": "prompt",
             "message": ["content": "Go"]],
            ["type": "assistant", "sessionId": "S", "timestamp": stamp(t + 1000), "uuid": "answer",
             "message": ["stop_reason": "end_turn", "content": [["type": "text", "text": "Response"]]]],
            ["type": "system", "sessionId": "S", "timestamp": stamp(t + 2000), "parentUuid": "answer",
             "subtype": "stop_hook_summary", "preventedContinuation": false, "hasOutput": false,
             "hookErrors": [String](), "hookAdditionalContext": [String](), "stopReason": ""]
        ]
    }

    @Test func completionSurvivesPollingAndPartialWritesWithoutDuplicateSigns() throws {
        defer { try? FileManager.default.removeItem(at: root) }
        let t = now(), file = project.appendingPathComponent("S.jsonl")
        let rows = completionRows(t)
        try append(file, jsonLine(rows[0]) + jsonLine(rows[1]))
        let source = ClaudeTranscriptSource(projectsDir: root.appendingPathComponent("projects"))
        #expect(source.poll(now: t + 1000).map(\.kind) == [.taskStart, .thinking])
        let line = try jsonLine(rows[2]), split = line.index(line.startIndex, offsetBy: 40)
        try append(file, String(line[..<split]))
        #expect(source.poll(now: t + 2000).isEmpty)
        try append(file, String(line[split...]))
        #expect(source.poll(now: t + 2500).map(\.kind) == [.finalAnswer, .taskEnd])
        try append(file, jsonLine(rows[1]) + jsonLine(rows[2]))
        #expect(source.poll(now: t + 3000).isEmpty)
    }

    @Test func startupReadsBackgroundVetoWithoutReplayingOldHookEvents() throws {
        defer { try? FileManager.default.removeItem(at: root) }
        let t = now(), file = project.appendingPathComponent("S.jsonl")
        for row in completionRows(t - 4000) { try append(file, jsonLine(row)) }
        let inbox = root.appendingPathComponent("hooks.jsonl")
        try append(inbox, jsonLine(["hook_event_name": "Stop", "session_id": "S", "prompt_id": "prompt",
            "background_tasks": [["status": "running", "type": "shell"]], "session_crons": [String]()]))
        let source = ClaudeTranscriptSource(projectsDir: root.appendingPathComponent("projects"))
        let hooks = HookInboxSource(url: inbox)
        hooks.onStop = { row, receivedAt in source.observeStopHook(row, receivedAt: receivedAt) }
        #expect(hooks.poll(now: t).isEmpty)
        let events = source.poll(now: t)
        #expect(!events.contains { $0.kind == .taskEnd || $0.kind == .finalAnswer })
    }

    @Test func delayedHookReceiptCannotRestartATurnAlreadyFinishedInTheTranscript() throws {
        defer { try? FileManager.default.removeItem(at: root) }
        let t = now(), file = project.appendingPathComponent("S.jsonl"), inbox = root.appendingPathComponent("hooks.jsonl")
        try append(inbox, "")
        let source = ClaudeTranscriptSource(projectsDir: root.appendingPathComponent("projects"))
        let hooks = HookInboxSource(url: inbox)
        hooks.prefersTranscript = { source.coversTranscript(at: $0) }
        #expect(hooks.poll(now: t).isEmpty)
        for row in completionRows(t) { try append(file, jsonLine(row)) }
        try append(inbox, jsonLine(["hook_event_name": "UserPromptSubmit", "session_id": "S",
            "transcript_path": file.path, "prompt": "Go"]))
        try append(inbox, jsonLine(["hook_event_name": "PreToolUse", "session_id": "S",
            "transcript_path": file.path, "tool_use_id": "already-finished", "tool_name": "Read"]))
        #expect(hooks.poll(now: t + 4000).isEmpty)
        let router = ActivityRouter(now: t)
        for event in source.poll(now: t + 4000) { router.ingest(event, now: event.ts) }
        router.settle(now: t + 6000)
        #expect(router.completedSession == "S")
        // A genuinely unavailable transcript still permits the optional hook fallback.
        try append(inbox, jsonLine(["hook_event_name": "PreToolUse", "session_id": "other",
            "transcript_path": root.appendingPathComponent("missing.jsonl").path,
            "tool_use_id": "fallback", "tool_name": "Read"]))
        #expect(hooks.poll(now: t + 5000).map(\.kind) == [.activityStart])
    }

    @Test func partialStopAtStartupStillDeliversItsVetoWhenCompleted() throws {
        defer { try? FileManager.default.removeItem(at: root) }
        let inbox = root.appendingPathComponent("hooks.jsonl")
        let line = try jsonLine(["hook_event_name": "Stop", "session_id": "S", "prompt_id": "prompt",
            "background_tasks": [["status": "running"]], "session_crons": [String]()])
        let cut = line.index(line.startIndex, offsetBy: 30)
        try append(inbox, String(line[..<cut]))
        let hooks = HookInboxSource(url: inbox)
        var observations = 0
        hooks.onStop = { _, _ in observations += 1; return [] }
        #expect(hooks.poll(now: 1000).isEmpty)
        #expect(observations == 0)
        try append(inbox, String(line[cut...]))
        #expect(hooks.poll(now: 2000).isEmpty)
        #expect(observations == 1)
    }

    @Test func hookInboxReadsOnlyNewRecordsAndRotates() throws {
        let inbox = root.appendingPathComponent("hooks.jsonl")
        try append(inbox, #"{"hook_event_name":"UserPromptSubmit","session_id":"H"}"# + "\n")
        let source = HookInboxSource(url: inbox)
        source.rotateBytes = 100
        #expect(source.poll(now: 1).isEmpty)               // 启动前的旧记录不回放
        try append(inbox, #"{"hook_event_name":"PreToolUse","session_id":"H","tool_name":"Read","tool_input":{"file_path":"a.png"},"tool_use_id":"t"}"# + "\n")
        let evs = source.poll(now: 2)
        #expect(evs.count == 1 && evs[0].activity == .view_image && evs[0].ts == 2)
        // 超过轮转阈值后被清空，之后的新记录仍能读到。
        let size = try FileManager.default.attributesOfItem(atPath: inbox.path)[.size] as? Int
        #expect(size == 0)
        try append(inbox, #"{"hook_event_name":"Stop","session_id":"H"}"# + "\n")
        #expect(source.poll(now: 3).isEmpty) // An attempted Stop alone cannot confirm completion.
    }
}
