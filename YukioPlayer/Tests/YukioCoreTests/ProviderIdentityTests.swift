import Testing
@testable import YukioCore

@Suite struct ProviderIdentityTests {
    @Test func identicalProviderSessionAndCallIDsStayIndependent() throws {
        let router = ActivityRouter(now: 0)
        for source in ["codex", "claude-transcript"] {
            router.ingest(.init(ts: 1000, source: source, session: "same-id", kind: .taskStart), now: 1000)
            router.ingest(.init(ts: 1001, source: source, session: "same-id", kind: .activityStart,
                eventID: "same-call", activity: .question_for_user, question: .init(text: source)), now: 1001)
        }
        let rows = router.sessionSummaries(now: 2000)
        #expect(rows.count == 2)
        #expect(Set(rows.compactMap { router.sourceOfSession($0.id) }) == ["codex", "claude-transcript"])
        let codex = try #require(router.routingSessionID(source: "codex", session: "same-id"))
        let claude = try #require(router.routingSessionID(source: "claude-transcript", session: "same-id"))
        #expect(codex != claude)
        #expect(router.sourceSessionID(codex) == "same-id" && router.sourceSessionID(claude) == "same-id")
        for id in [codex, claude] {
            #expect(router.pinSession(id, now: 2000))
            router.settle(now: 2000)
            let pending = try #require(router.askingQuestion)
            #expect(pending.targetSession == "same-id")
            #expect(pending.question.text == router.sourceOfSession(id))
        }
        // Hooks and transcript are two observations of the same Claude task.
        router.ingest(.init(ts: 1001, source: "claude-hook", session: "same-id", kind: .activityStart,
            eventID: "same-call", activity: .question_for_user, question: .init(text: "duplicate")), now: 2100)
        #expect(router.sessionSummaries(now: 2100).count == 2)
        #expect(router.sessions[claude]?.open.count == 1)
        router.ingest(.init(ts: 2500, source: "codex", session: "same-id", kind: .activityFailed, eventID: "same-call"), now: 2500)
        #expect(router.sessions[codex]?.open.isEmpty == true)
        #expect(router.sessions[claude]?.open.count == 1)
        #expect(router.askingQuestion?.source == "claude-transcript")
        router.ingest(.init(ts: 2600, source: "codex", session: "*", kind: .sourceLost), now: 2600)
        #expect(router.sessions[claude]?.taskActive == true)
        router.reset(now: 3000)
        #expect(router.routingSessionID(source: "codex", session: "same-id") == nil)
    }
}
