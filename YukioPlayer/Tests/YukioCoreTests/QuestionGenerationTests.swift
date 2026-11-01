import Testing
@testable import YukioCore

@Suite struct QuestionGenerationTests {
    private func ask(_ h: Harness, id: String = "reused") {
        h.router.ingest(PetEvent(ts: h.now, source: "test", session: h.session,
            kind: .activityStart, eventID: id, activity: .question_for_user,
            question: PetQuestion(text: "Choose")), now: h.now)
        h.run(to: h.now + 1000)
    }

    @Test func sameCallIDInNextTurnHasIndependentDraftIdentity() throws {
        let h = Harness()
        h.send(.taskStart); ask(h)
        let first = try #require(h.router.askingQuestion)
        h.send(.taskAbort); h.run(to: 5000)
        h.send(.taskStart); ask(h)
        let second = try #require(h.router.askingQuestion)
        #expect(QuestionPresentationState.Key(first) != QuestionPresentationState.Key(second))
    }

    @Test func answeredCallIDCanBeReusedInNextTurn() throws {
        let h = Harness()
        h.send(.taskStart); ask(h)
        h.send(.activityEnd, id: "reused")
        h.send(.taskAbort); h.run(to: 5000)
        h.send(.taskStart); ask(h)
        #expect(h.router.askingQuestion?.callID == "reused")
    }

    @Test func lateOldEndDoesNotCloseCurrentQuestion() throws {
        let h = Harness()
        h.send(.taskStart); ask(h)
        let oldTime = h.now
        h.send(.taskAbort); h.run(to: 5000)
        h.send(.taskStart); ask(h)
        h.router.ingest(PetEvent(ts: oldTime, source: "test", session: h.session,
            kind: .activityEnd, eventID: "reused"), now: h.now)
        #expect(h.router.askingQuestion?.callID == "reused")
    }

    @Test func hundredsOfOtherCardsCannotDiscardAnUnsentDraft() {
        var state = QuestionPresentationState()
        let first = QuestionPresentationState.Key(.init(session: "a", callID: "q", question: PetQuestion(text: "A")))
        state.saveDraft("  unfinished 中文  ", picked: [1], for: first)
        state.dismiss(first)
        for index in 0..<600 {
            state.dismiss(.init(.init(session: "other-\(index)", callID: "q", question: PetQuestion(text: "B"))))
        }
        state.reopen(first)
        #expect(state.draft(for: first) == "  unfinished 中文  ")
        #expect(state.picked(for: first) == [1])
    }

    @Test(arguments: 0..<10) func switchingRetryAndLateCallbacksStayWithTheirRequest(_ repetition: Int) throws {
        let h = Harness()
        h.send(.taskStart); ask(h)
        let old = try #require(h.router.askingQuestion)
        let a = QuestionPresentationState.Key(old)
        let b = QuestionPresentationState.Key(.init(session: "other", callID: old.callID,
            question: old.question, source: "claude-transcript", generation: "other-turn"))
        var state = QuestionPresentationState()
        state.saveDraft("A 中文 \(repetition)", picked: [1], for: a)
        state.saveDraft("B", picked: [0], for: b)
        let firstToken = state.beginSubmission(a)
        let firstAttempt = try #require(firstToken)
        let duplicate = state.beginSubmission(a)
        #expect(duplicate == nil)
        state.dismiss(a); state.reopen(a)
        let firstFinished = state.finishSubmission(a, token: firstAttempt)
        #expect(firstFinished)
        state.setNotice("Failed", for: a)
        let retryToken = state.beginSubmission(a)
        let retry = try #require(retryToken)
        let staleFinished = state.finishSubmission(a, token: firstAttempt)
        #expect(!staleFinished)
        #expect(state.isSending(a) && !state.isSending(b))
        h.send(.taskAbort); h.run(to: 5000); h.send(.taskStart); ask(h)
        let current = try #require(h.router.askingQuestion)
        #expect(!h.router.acknowledgeQuestion(old, now: h.now))
        #expect(h.router.containsQuestion(current))
        let retryFinished = state.finishSubmission(a, token: retry)
        #expect(retryFinished)
        #expect(state.draft(for: a) == "A 中文 \(repetition)" && state.picked(for: a) == [1])
        #expect(state.draft(for: b) == "B" && state.picked(for: b) == [0])
        h.router.reset(now: h.now)
        #expect(!h.router.containsQuestion(current))
        #expect(!h.router.acknowledgeQuestion(current, now: h.now))
    }
}
