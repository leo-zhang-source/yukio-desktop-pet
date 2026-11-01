import Foundation
import Testing
@testable import YukioCore

@Suite struct Round2StatusTests {
    @Test func claudeStopIsNotWholeTaskCompletion() {
        let h = Harness()
        h.send(.taskStart, source: ClaudeHookParser.source)
        h.run(to: 1000)
        let events = ClaudeHookParser().events(from: ["hook_event_name": "Stop", "session_id": h.session], receivedAt: h.now)
        for e in events { h.router.ingest(e, now: h.now) }
        h.run(to: 6000)
        #expect(h.router.completedSession == nil)
        #expect(h.router.displayed == .idle)
        #expect(!h.router.sessionSummaries(now: h.now).contains { $0.live || $0.raisedSign })
    }

    @Test func endedClaudeCannotHideAnotherWorkingChat() {
        let h = Harness()
        h.send(.taskStart, session: "A", source: ClaudeHookParser.source)
        h.send(.taskStart, session: "B", source: ClaudeHookParser.source)
        h.run(to: 1000)
        for e in ClaudeHookParser().events(from: ["hook_event_name": "Stop", "session_id": "A"], receivedAt: h.now) { h.router.ingest(e, now: h.now) }
        h.run(to: 6000)
        #expect(h.router.focusedSession == "B")
        #expect(h.router.displayed == .thinking)
    }

    @Test func lateStartDoesNotReopenAnEndedTurn() {
        let h = Harness()
        h.send(.taskStart, source: ClaudeHookParser.source)
        h.run(to: 1000)
        for e in ClaudeHookParser().events(from: ["hook_event_name": "Stop", "session_id": h.session], receivedAt: h.now) { h.router.ingest(e, now: h.now) }
        h.router.ingest(.init(ts: 0, source: ClaudeTranscriptParser.source, session: h.session, kind: .taskStart), now: 2000)
        h.run(to: 6000)
        #expect(!h.router.sessionSummaries(now: h.now).contains { $0.live })
    }

    @Test func claudeDesktopAddressWithoutSchemeIsRecognized() {
        let id = "local_12345678-1234-1234-1234-123456789abc"
        #expect(VisibleChat(url: "claude.ai/epitaxy/" + id)?.id == id)
        #expect(VisibleChat(url: "claude.ai.attacker.test/epitaxy/" + id) == nil)
        #expect(VisibleChat(url: "http://claude.ai/epitaxy/" + id) == nil)
    }
}
