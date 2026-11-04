import Testing
@testable import YukioCore

@Suite struct ClaudeQuestionIdentityTests {
    private let question = PetQuestion(text: "C_ONE or C_TWO?")
    private func start(_ router: ActivityRouter, id: String, related: String? = nil,
                       question: PetQuestion? = nil, session: String = "C", source: String = "claude-transcript", at: Double = 1) {
        router.ingest(PetEvent(ts: at, source: source, session: session, kind: .activityStart,
                              eventID: id, activity: .question_for_user, question: question ?? self.question,
                              questionCallID: related), now: at)
        _ = router.focusSessionTemporarily(session, now: at)
        _ = router.tick(now: at + 10000)
    }
    private func pending(_ router: ActivityRouter) throws -> ActivityRouter.PendingQuestion {
        try #require(router.askingQuestion)
    }

    @Test(arguments: [false, true]) func hookAndTranscriptKeepDraftAcrossExpiryAndApproval(hookFirst: Bool) throws {
        let r = ActivityRouter(now: 0)
        let hook = "yukio-claude:request:0", raw = "toolu_C"
        start(r, id: hookFirst ? hook : raw, related: hookFirst ? raw : nil)
        let first = try pending(r)
        var ui = QuestionPresentationState()
        ui.saveDraft("测试成功", picked: [1], for: .init(first))
        start(r, id: hookFirst ? raw : hook, related: hookFirst ? nil : raw, at: 2)
        let second = try pending(r)
        #expect(QuestionPresentationState.Key(first) == .init(second))
        #expect(ui.draft(for: .init(second)) == "测试成功")
        r.ingest(PetEvent(ts: 3, source: "claude-transcript", session: "C", kind: .activityEnd, eventID: hook), now: 3)
        let approval = ApprovalQuestion.make(provider: "Claude", details: "AskUserQuestion approval")
        start(r, id: "yukio-claude:approval:0", related: raw, question: approval, at: 4)
        let approvalPending = try pending(r)
        #expect(ui.draft(for: .init(approvalPending)).isEmpty)
        #expect(QuestionPresentationState.Key(first) != .init(approvalPending))
        #expect(r.acknowledgeQuestion(approvalPending, now: 5))
        _ = r.tick(now: 10005)
        let restored = try pending(r)
        #expect(restored.callID == raw)
        #expect(ui.draft(for: .init(restored)) == "测试成功")
        #expect(ui.picked(for: .init(restored)) == [1])
        // Expiring the transport must not retire the transcript's live question.
        #expect(r.containsQuestion(restored))
        #expect(!r.containsQuestion(first.callID == hook ? first : second))
    }

    @Test func similarTextDifferentCallOrChangedQuestionDoesNotShareDraft() throws {
        let r = ActivityRouter(now: 0)
        start(r, id: "toolu_C")
        let original = try pending(r)
        var ui = QuestionPresentationState()
        ui.saveDraft("original", picked: [], for: .init(original))
        start(r, id: "yukio-claude:other:0", related: "toolu_OTHER", at: 2)
        #expect(ui.draft(for: .init(try pending(r))).isEmpty)
        start(r, id: "yukio-claude:changed:0", related: "toolu_C", question: PetQuestion(text: "Changed?"), at: 3)
        #expect(ui.draft(for: .init(try pending(r))).isEmpty)
    }

    @Test func newTurnReusingCallIDCannotReceiveOldDraftOrReceipt() throws {
        let r = ActivityRouter(now: 0)
        start(r, id: "toolu_C")
        let old = try pending(r)
        var ui = QuestionPresentationState()
        ui.saveDraft("old", picked: [], for: .init(old))
        r.ingest(PetEvent(ts: 20000, source: "claude-transcript", session: "C", kind: .taskStart), now: 20000)
        start(r, id: "yukio-claude:new:0", related: "toolu_C", at: 20001)
        #expect(ui.draft(for: .init(try pending(r))).isEmpty)
        #expect(!r.acknowledgeQuestion(old, now: 20002))
    }

    @Test func sessionAndProviderCannotAlias() throws {
        let r = ActivityRouter(now: 0)
        start(r, id: "toolu_C")
        let old = try pending(r)
        var ui = QuestionPresentationState()
        ui.saveDraft("C only", picked: [], for: .init(old))
        start(r, id: "yukio-claude:B:0", related: "toolu_C", session: "B", at: 2)
        #expect(ui.draft(for: .init(try pending(r))).isEmpty)
        let other = ActivityRouter(now: 0)
        start(other, id: "toolu_C", source: "codex", at: 1)
        let raw = try pending(other)
        start(other, id: "yukio-claude:foreign:0", related: "toolu_C", source: "codex", at: 2)
        #expect(QuestionPresentationState.Key(raw) != .init(try pending(other)))
    }
}
