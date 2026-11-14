import Foundation
import Testing
@testable import YukioCore

@Suite struct ClaudeCompletionTests {
    private func row(_ type: String, _ ms: Double, session: String = "claude-a",
                     fields: [String: Any] = [:]) -> [String: Any] {
        var value: [String: Any] = ["type": type, "sessionId": session,
            "timestamp": ISO8601DateFormatter().string(from: Date(timeIntervalSince1970: ms / 1000))]
        value.merge(fields) { _, new in new }
        return value
    }

    private func answer(_ ms: Double, stop: String = "end_turn", id: String = "answer-a",
                        session: String = "claude-a", blocks: [[String: Any]]? = nil) -> [String: Any] {
        row("assistant", ms, session: session, fields: ["uuid": id, "message": [
            "role": "assistant", "stop_reason": stop,
            "content": blocks ?? [["type": "text", "text": "A public response"]]]])
    }

    private func summary(_ ms: Double, parent: String = "answer-a", session: String = "claude-a",
                         extra: [String: Any] = [:]) -> [String: Any] {
        var fields: [String: Any] = ["subtype": "stop_hook_summary", "parentUuid": parent,
            "preventedContinuation": false, "hasOutput": false, "hookErrors": [String](),
            "hookAdditionalContext": [String](), "stopReason": ""]
        fields.merge(extra) { _, new in new }
        return row("system", ms, session: session, fields: fields)
    }

    private func start(_ parser: ClaudeTranscriptParser, prompt: String = "prompt-a", at: Double = 0) {
        _ = parser.events(from: row("user", at, fields: ["promptId": prompt, "message": ["content": "Continue"]]))
    }

    @Test func completionRequiresAnExactSuccessfulClientSummaryAndEmitsOnce() {
        let parser = ClaudeTranscriptParser()
        start(parser)
        #expect(parser.events(from: answer(1000)).map(\.kind) == [.thinking])
        #expect(parser.events(from: summary(2000, parent: "other-answer")).isEmpty)
        #expect(parser.events(from: summary(2000, session: "claude-b")).isEmpty)
        #expect(parser.events(from: summary(3000)).map(\.kind) == [.finalAnswer, .taskEnd])
        #expect(parser.events(from: summary(3000)).isEmpty)
        #expect(parser.events(from: answer(1000)).isEmpty)
        #expect(parser.events(from: summary(4000)).isEmpty)
    }

    @Test func interactiveCLIUsesItsCorrelatedDurationRecord() {
        let parser = ClaudeTranscriptParser()
        var reply = answer(1000); reply["entrypoint"] = "cli"
        _ = parser.events(from: reply)
        #expect(parser.events(from: row("system", 2000, fields: ["subtype": "turn_duration",
            "parentUuid": "foreign", "entrypoint": "cli", "durationMs": 1200])).isEmpty)
        #expect(parser.events(from: row("system", 3000, fields: ["subtype": "turn_duration",
            "parentUuid": "answer-a", "entrypoint": "cli", "durationMs": 1200])).map(\.kind) == [.finalAnswer, .taskEnd])
    }

    @Test func headlessCLIUsesAnExactPersistedLeaf() {
        for entry in ["sdk-cli", "claude-desktop", "unknown"] {
            let parser = ClaudeTranscriptParser()
            var reply = answer(1000); reply["entrypoint"] = entry
            _ = parser.events(from: reply)
            let leaf: [String: Any] = ["type": "last-prompt", "sessionId": "claude-a", "leafUuid": "answer-a"]
            #expect(parser.events(from: leaf).map(\.kind) == (entry == "sdk-cli" ? [.finalAnswer, .taskEnd] : []))
            #expect(parser.events(from: leaf).isEmpty)
        }
    }

    @Test func backgroundCompletionNotificationContinuesTheSameHumanTask() {
        let parser = ClaudeTranscriptParser(); start(parser)
        _ = parser.events(from: row("user", 1000, fields: ["toolUseResult": ["backgroundTaskId": "job-a"],
            "message": ["content": [["type": "tool_result", "tool_use_id": "call-a", "content": "Started"]]]]))
        var reply = answer(2000); reply["entrypoint"] = "sdk-cli"
        _ = parser.events(from: reply)
        #expect(parser.events(from: ["type": "last-prompt", "sessionId": "claude-a", "leafUuid": "answer-a"]).isEmpty)
        #expect(parser.events(from: row("user", 3000, fields: ["promptId": "notification",
            "origin": ["kind": "task-notification"], "promptSource": "system", "message": ["content":
            "<task-notification><task-id>job-a</task-id><status>completed</status></task-notification>"]])).map(\.kind) == [.thinking])
        reply = answer(4000, id: "final"); reply["entrypoint"] = "sdk-cli"
        _ = parser.events(from: reply)
        #expect(parser.events(from: ["type": "last-prompt", "sessionId": "claude-a", "leafUuid": "final"]).map(\.kind) == [.finalAnswer, .taskEnd])
    }

    @Test func earlierBackgroundServicesDoNotKeepLaterRequestsWorkingForever() {
        let parser = ClaudeTranscriptParser(); start(parser, prompt: "earlier")
        let registry: [[String: Any]] = [["id": "preview", "type": "shell", "status": "running"],
                                        ["id": "watcher", "type": "monitor", "status": "running"]]
        _ = parser.observeStopHook(["hook_event_name": "Stop", "session_id": "claude-a", "prompt_id": "earlier",
                                   "background_tasks": registry, "session_crons": []], receivedAt: 1000)
        start(parser, prompt: "current", at: 2000)
        _ = parser.events(from: answer(3000))
        _ = parser.observeStopHook(["hook_event_name": "Stop", "session_id": "claude-a", "prompt_id": "current",
                                   "background_tasks": registry, "session_crons": []], receivedAt: 4000)
        #expect(parser.events(from: summary(5000)).map(\.kind) == [.finalAnswer, .taskEnd])
    }

    @Test func notificationPromptDoesNotInheritAnOlderStopVeto() {
        let parser = ClaudeTranscriptParser(); start(parser)
        _ = parser.observeStopHook(["hook_event_name": "Stop", "session_id": "claude-a", "prompt_id": "prompt-a",
            "background_tasks": [["id": "job-a", "status": "running"]], "session_crons": []], receivedAt: 10000)
        _ = parser.events(from: row("user", 2000, fields: ["promptId": "notification",
            "origin": ["kind": "task-notification"], "promptSource": "system", "message": ["content":
            "<task-notification><task-id>job-a</task-id><status>completed</status></task-notification>"]]))
        _ = parser.events(from: answer(3000))
        #expect(parser.events(from: summary(4000)).map(\.kind) == [.finalAnswer, .taskEnd])
    }

    @Test func incompleteAndBlockedHookSummariesNeverConfirmCompletion() {
        for extra: [String: Any] in [
            ["preventedContinuation": true], ["hasOutput": true], ["hookErrors": ["continue"]],
            ["hookAdditionalContext": ["continue"]], ["stopReason": "continue"],
            ["preventedContinuation": NSNull()], ["hookErrors": NSNull()]
        ] {
            let parser = ClaudeTranscriptParser()
            start(parser); _ = parser.events(from: answer(1000))
            #expect(parser.events(from: summary(2000, extra: extra)).map(\.kind) == [.thinking])
        }
    }

    @Test func laterActivityOrNewRequestInvalidatesThePreviousResponse() {
        for continuation in [
            row("api-request", 2000, fields: ["querySource": "sdk"]),
            answer(2000, stop: "tool_use", id: "working", blocks: [["type": "thinking"]]),
            row("user", 2000, fields: ["promptId": "prompt-b", "message": ["content": "Continue"]]),
            row("system", 2000, fields: ["subtype": "api_error"])
        ] {
            let parser = ClaudeTranscriptParser()
            start(parser); _ = parser.events(from: answer(1000))
            _ = parser.events(from: continuation)
            #expect(parser.events(from: summary(3000)).isEmpty)
        }
    }

    @Test func stopIsOnlyAnAttemptAndBackgroundWorkVetoesTheMatchingTurn() {
        for payload: [String: Any] in [
            ["background_tasks": [["type": "shell", "status": "running"]], "session_crons": []],
            ["background_tasks": [], "session_crons": [["id": "scheduled"]]],
            [:]
        ] {
            let parser = ClaudeTranscriptParser()
            start(parser)
            var hook: [String: Any] = ["hook_event_name": "Stop", "session_id": "claude-a", "prompt_id": "prompt-a"]
            hook.merge(payload) { _, new in new }
            #expect(ClaudeHookParser().events(from: hook, receivedAt: 2000).isEmpty)
            // Hooks can be read before the corresponding transcript batch.
            _ = parser.observeStopHook(hook, receivedAt: 2000)
            _ = parser.events(from: answer(1000))
            #expect(parser.events(from: summary(3000)).map(\.kind) == [.thinking])
            // A later response and empty registry can complete normally.
            _ = parser.events(from: answer(4000, id: "answer-b"))
            hook["background_tasks"] = [Any](); hook["session_crons"] = [Any]()
            _ = parser.observeStopHook(hook, receivedAt: 5000)
            #expect(parser.events(from: summary(6000, parent: "answer-b")).map(\.kind) == [.finalAnswer, .taskEnd])
        }
    }

    @Test func oldOrForeignStopCannotCancelThisTurnsCompletion() {
        for (session, prompt) in [("claude-b", "prompt-a"), ("claude-a", "previous-prompt")] {
            let parser = ClaudeTranscriptParser()
            start(parser); _ = parser.events(from: answer(1000))
            #expect(parser.observeStopHook(["hook_event_name": "Stop", "session_id": session,
                "prompt_id": prompt, "background_tasks": [["status": "running"]], "session_crons": []], receivedAt: 2000).isEmpty)
            #expect(parser.events(from: summary(3000)).map(\.kind) == [.finalAnswer, .taskEnd])
        }
    }

    @Test func childAgentsAndContextRecordsCannotFinishTheMainTurn() {
        for extra: [String: Any] in [["isSidechain": true], ["agentId": "child"], ["isMeta": true], ["isCompactSummary": true]] {
            let parser = ClaudeTranscriptParser()
            start(parser)
            var child = answer(1000); child.merge(extra) { _, new in new }
            #expect(parser.events(from: child).isEmpty)
            #expect(parser.events(from: summary(2000)).isEmpty)
        }
        #expect(ClaudeHookParser().events(from: ["hook_event_name": "StopFailure", "session_id": "claude-a",
            "agent_id": "child"], receivedAt: 2000).isEmpty)
    }

    @Test func confirmedCompletionRaisesAndKeepsTheSign() {
        let parser = ClaudeTranscriptParser(), h = Harness(session: "claude-a")
        for raw in [row("user", 0, fields: ["message": ["content": "Continue"]]), answer(1000), summary(2000)] {
            for event in parser.events(from: raw) {
                h.run(to: event.ts); h.router.ingest(event, now: event.ts)
            }
        }
        h.run(to: 20000)
        #expect(h.router.completedSession == "claude-a")
        #expect(h.states == [.thinking, .respond, .task_complete])
    }

    @Test func ongoingThinkingClearsAnUnconfirmedFinalAnswer() {
        let h = Harness()
        h.send(.taskStart); h.run(to: 1000); h.send(.finalAnswer)
        h.run(to: 2000); h.send(.thinking); h.send(.taskEnd)
        h.run(to: 10000)
        #expect(!h.states.contains(.task_complete))
    }

    @Test func splitBlocksFromTheSameResponsePreserveToolEvidence() {
        let parser = ClaudeTranscriptParser()
        var tool = answer(1000, blocks: [["type": "tool_use", "name": "Read", "id": "r"]])
        var text = answer(2000)
        for row in ["tool", "text"] {
            var value = row == "tool" ? tool : text
            var message = value["message"] as! [String: Any]
            message["id"] = "one-api-response"; value["message"] = message
            if row == "tool" { tool = value } else { text = value }
        }
        _ = parser.events(from: tool); _ = parser.events(from: text)
        #expect(parser.events(from: summary(3000)).isEmpty)
    }

    @Test func unrelatedStopDoesNotEraseTheCurrentBackgroundVeto() {
        let parser = ClaudeTranscriptParser()
        start(parser)
        for prompt in ["prompt-a", "old-prompt"] {
            _ = parser.observeStopHook(["hook_event_name": "Stop", "session_id": "claude-a", "prompt_id": prompt,
                "background_tasks": [["status": "running"]], "session_crons": []], receivedAt: 2000)
        }
        _ = parser.events(from: answer(1000))
        #expect(parser.events(from: summary(3000)).map(\.kind) == [.thinking])
    }

    @Test func helperRequestsDoNotInvalidateARealResponse() {
        let parser = ClaudeTranscriptParser()
        _ = parser.events(from: answer(1000))
        #expect(parser.events(from: row("api-request", 2000, fields: ["querySource": "title"])).isEmpty)
        #expect(parser.events(from: summary(3000)).map(\.kind) == [.finalAnswer, .taskEnd])
    }

    @Test func lateCompletionCannotEndNewerWorkWithinTheSameTurn() {
        let h = Harness()
        h.send(.taskStart); h.run(to: 1000)
        h.send(.activityStart, id: "r", .read_file)
        h.run(to: 10000)
        for kind in [PetEvent.Kind.finalAnswer, .taskEnd] {
            h.router.ingest(PetEvent(ts: 500, source: "test", session: "s1", kind: kind), now: h.now)
        }
        h.run(to: 15000)
        #expect(h.router.displayed == .read_file)
        #expect(!h.states.contains(.task_complete))
    }

    @Test func rejectedOldRecordsDoNotKeepAStaleTaskAlive() {
        let h = Harness()
        h.send(.taskStart); h.run(to: 1000); h.send(.thinking)
        h.run(to: 700000)
        #expect(h.router.displayed == .idle)
        h.router.ingest(PetEvent(ts: 0, source: "test", session: "s1", kind: .thinking), now: h.now)
        h.run(to: 710000)
        #expect(h.router.displayed == .idle)
    }

    @Test func stopSequenceDoesNotRaiseThenWithdrawCompletion() {
        let parser = ClaudeTranscriptParser(), h = Harness(session: "claude-a")
        for event in parser.events(from: row("user", 0, fields: ["message": ["content": "Continue"]])) {
            h.router.ingest(event, now: event.ts)
        }
        h.run(to: 1000)
        for event in parser.events(from: answer(1000, stop: "stop_sequence")) {
            h.router.ingest(event, now: event.ts)
        }
        // The real trace resumed after 5.813 seconds, beyond the 3-second sign delay.
        h.run(to: 6800)
        #expect(!h.states.contains(.respond))
        #expect(!h.states.contains(.task_complete))
        #expect(h.router.completedSession == nil)
        for event in parser.events(from: answer(7000, stop: "tool_use", blocks: [
            ["type": "tool_use", "name": "Read", "id": "read-a", "input": ["file_path": "demo.txt"]]
        ])) { h.router.ingest(event, now: event.ts) }
        h.run(to: 9000)
        #expect(h.router.displayed == .read_file)
    }

    @Test func assistantStopReasonCannotEndAMessageThatStillRequestsTools() {
        for blocks in [
            [["type": "text", "text": "Working"], ["type": "tool_use", "name": "Read", "id": "r"]],
            [["type": "tool_use", "name": "Read", "id": "r"], ["type": "text", "text": "Working"]]
        ] {
            let events = ClaudeTranscriptParser().events(from: answer(1000, blocks: blocks))
            #expect(!events.contains { $0.kind == .taskEnd || $0.kind == .finalAnswer })
            #expect(events.contains { $0.kind == .activityStart })
        }
    }

    @Test func apiRequestIsEvidenceThatTheTurnContinues() {
        let events = ClaudeTranscriptParser().events(from: row("api-request", 2000, fields: ["querySource": "sdk"]))
        #expect(events.map(\.kind) == [.thinking])
    }

    @Test func lateFinalAnswerCannotAttachToANewerRequest() {
        let h = Harness()
        h.send(.taskStart)
        h.run(to: 10000)
        h.send(.taskStart)
        h.router.ingest(PetEvent(ts: 5000, source: "test", session: "s1", kind: .finalAnswer), now: 10001)
        h.send(.taskEnd)
        h.run(to: 15000)
        #expect(!h.states.contains(.task_complete))
    }

    @Test func replayedTerminalPairCannotRearmADismissedCompletion() {
        let h = Harness()
        h.send(.taskStart)
        h.run(to: 1000)
        h.send(.finalAnswer); h.send(.taskEnd)
        h.run(to: 6000)
        #expect(h.router.dismissCompletion(now: h.now))
        for kind in [PetEvent.Kind.finalAnswer, .taskEnd] {
            h.router.ingest(PetEvent(ts: 1000, source: "test", session: "s1", kind: kind), now: 6000)
        }
        h.run(to: 10000)
        #expect(h.router.completedSession == nil)
    }
}
