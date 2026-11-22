import Foundation
import Testing
@testable import YukioCore

/// Claude Desktop ends a turn with a "next step" box. Only a box the client itself marks as
/// blocking is a question; a follow-up offer or a plain recap is a finished turn.
/// The four boxes below are the shapes recorded in one real chat.
@Suite struct NextStepBoxTests {
    init() { L10n.language = .chinese }

    private func row(_ type: String, _ ms: Double, _ fields: [String: Any]) -> [String: Any] {
        var value: [String: Any] = ["type": type, "sessionId": "claude-a",
            "timestamp": ISO8601DateFormatter().string(from: Date(timeIntervalSince1970: ms / 1000))]
        value.merge(fields) { _, new in new }
        return value
    }

    /// prompt → next-step box → its receipt → closing answer → the client's stop summary.
    private func turn(_ parser: ClaudeTranscriptParser, at base: Double, box: [String: Any]?, tag: String) -> [PetEvent] {
        var out = parser.events(from: row("user", base, ["uuid": "prompt-\(tag)", "promptId": "prompt-\(tag)",
                                                         "message": ["content": "继续"]]))
        if let box {
            out += parser.events(from: row("assistant", base + 100, ["uuid": "box-\(tag)", "message": [
                "role": "assistant", "id": "msg-box-\(tag)", "stop_reason": "tool_use",
                "content": [["type": "tool_use", "id": "call-\(tag)", "name": "mcp__ccd_turn__wrap_up", "input": box]]]]))
            out += parser.events(from: row("user", base + 200, ["uuid": "receipt-\(tag)", "message": [
                "role": "user", "content": [["type": "tool_result", "tool_use_id": "call-\(tag)", "content": "Shown"]]]]))
        }
        out += parser.events(from: row("assistant", base + 300, ["uuid": "answer-\(tag)", "message": [
            "role": "assistant", "id": "msg-answer-\(tag)", "stop_reason": "end_turn",
            "content": [["type": "text", "text": "结果说明"]]]]))
        out += parser.events(from: row("system", base + 400, ["subtype": "stop_hook_summary", "parentUuid": "answer-\(tag)",
            "preventedContinuation": false, "hasOutput": false, "hookErrors": [String](),
            "hookAdditionalContext": [String](), "stopReason": ""]))
        return out
    }

    private func end(_ events: [PetEvent]) -> PetEvent? { events.last { $0.kind == .taskEnd } }

    @Test func onlyABoxMarkedBlockingEndsTheTurnAsAQuestion() throws {
        let parser = ClaudeTranscriptParser()
        let blocking = try #require(end(turn(parser, at: 0, box: [
            "recap": "修复版已构建。", "ask": "现在把雪绪换成修复版 66.1 吗？",
            "actions": [["label": "现在安装"], ["label": "先不装"]], "blocked": true], tag: "a")))
        #expect(blocking.activity == .question_for_user)
        #expect(blocking.detail == "现在把雪绪换成修复版 66.1 吗？")

        // A follow-up offer with buttons: the turn is done, this is a suggested next step.
        let offer = try #require(end(turn(parser, at: 10_000, box: [
            "recap": "实测通过。", "ask": "要把这次修复合回本地维护入口吗？",
            "actions": [["label": "合回维护入口"], ["label": "先不合"]]], tag: "b")))
        #expect(offer.activity == nil && offer.detail == nil)

        let recap = try #require(end(turn(parser, at: 20_000, box: ["recap": "已合回。"], tag: "c")))
        #expect(recap.activity == nil && recap.detail == nil)

        let plain = try #require(end(turn(parser, at: 30_000, box: nil, tag: "d")))
        #expect(plain.activity == nil && plain.detail == nil)
    }

    @Test func theFlagMustBeARealTrueAndComeWithAQuestion() throws {
        let parser = ClaudeTranscriptParser()
        let boxes: [[String: Any]] = [
            ["recap": "r", "ask": "要继续吗？", "blocked": false],
            ["recap": "r", "ask": "要继续吗？", "blocked": 1],
            ["recap": "r", "ask": "要继续吗？", "blocked": "true"],
            ["recap": "r", "blocked": true],
            ["recap": "r", "ask": "  \n ", "blocked": true],
        ]
        for (index, box) in boxes.enumerated() {
            let ended = try #require(end(turn(parser, at: Double(index) * 10_000, box: box, tag: "\(index)")))
            #expect(ended.activity == nil, "\(box)")
        }
        let long = String(repeating: "问", count: 500) + "？"
        #expect(ClaudeTranscriptParser.blockingQuestion(nextStep: ["ask": long, "blocked": true])?.count == 200)
        #expect(ClaudeTranscriptParser.blockingQuestion(nextStep: ["ask": "第一行\n  第二行", "blocked": true]) == "第一行 第二行")
    }

    @Test func aLaterBoxOrANewRequestWithdrawsTheQuestion() throws {
        let parser = ClaudeTranscriptParser()
        _ = parser.events(from: row("user", 0, ["uuid": "p1", "promptId": "p1", "message": ["content": "开始"]]))
        func box(_ ms: Double, _ id: String, _ input: [String: Any]) {
            _ = parser.events(from: row("assistant", ms, ["uuid": "box-\(id)", "message": ["role": "assistant", "id": "m-\(id)",
                "content": [["type": "tool_use", "id": id, "name": "mcp__ccd_turn__wrap_up", "input": input]]]]))
            _ = parser.events(from: row("user", ms + 50, ["uuid": "r-\(id)", "message": ["role": "user",
                "content": [["type": "tool_result", "tool_use_id": id, "content": "Shown"]]]]))
        }
        box(100, "one", ["recap": "r", "ask": "先选方案？", "blocked": true])
        box(300, "two", ["recap": "都做完了。"])
        _ = parser.events(from: row("assistant", 500, ["uuid": "answer-1", "message": ["role": "assistant", "id": "m-a1",
            "stop_reason": "end_turn", "content": [["type": "text", "text": "完成"]]]]))
        let first = parser.events(from: row("system", 600, ["subtype": "stop_hook_summary", "parentUuid": "answer-1",
            "preventedContinuation": false, "hasOutput": false, "hookErrors": [String](),
            "hookAdditionalContext": [String](), "stopReason": ""]))
        #expect(try #require(end(first)).activity == nil)

        // The user answers before the client's stop summary arrives: the next turn starts clean.
        box(1000, "three", ["recap": "r", "ask": "先选方案？", "blocked": true])
        #expect(try #require(end(turn(parser, at: 2000, box: nil, tag: "next"))).activity == nil)
    }

    // MARK: What she shows

    private func harness() -> Harness {
        var config = RouterConfig()
        config.completeArmMs = 8000
        config.respondHoldMs = 3000
        return Harness(config: config)
    }

    private func finish(_ h: Harness, asking question: String?) {
        h.send(.taskStart); h.run(to: h.now + 3000)
        h.send(.finalAnswer)
        h.router.ingest(PetEvent(ts: h.now, source: "test", session: h.session, kind: .taskEnd,
                                 activity: question == nil ? nil : .question_for_user, detail: question), now: h.now)
    }

    @Test func aBlockingQuestionRaisesTheQuestionSignAndTheOfferRaisesTheDoneSign() {
        let asked = harness()
        finish(asked, asking: "现在安装吗？")
        asked.run(to: 60_000)
        #expect(asked.states.contains(.question_for_user) && !asked.states.contains(.task_complete))
        #expect(asked.router.handoffQuestionSession == asked.session)
        #expect(asked.router.completedSession == nil)
        #expect(asked.router.askingQuestion == nil)   // no answer card: the turn is over
        #expect(asked.router.statusLine(now: asked.now)?.current == "现在安装吗？ · 点她跳过去")
        #expect(asked.router.sessionSummaries(now: asked.now).first?.raisedSign == true)

        let offered = harness()
        finish(offered, asking: nil)
        offered.run(to: 60_000)
        #expect(offered.states.contains(.task_complete) && !offered.states.contains(.question_for_user))
        #expect(offered.router.completedSession == offered.session)
        #expect(offered.router.handoffQuestionSession == nil)
    }

    /// Seeing a question is not answering it; seeing a finished turn is enough.
    @Test func anOpenChatLowersTheDoneSignButNotTheQuestionSign() {
        let asked = harness()
        asked.router.visibleChatSessions = [asked.session]
        finish(asked, asking: "现在安装吗？")
        asked.run(to: 60_000)
        #expect(asked.router.handoffQuestionSession == asked.session)

        let offered = harness()
        finish(offered, asking: nil)
        offered.run(to: 20_000)
        #expect(offered.router.completedSession == offered.session)
        offered.router.visibleChatSessions = [offered.session]
        offered.run(to: 21_000)
        #expect(offered.router.completedSession == nil)
    }

    @Test func clickingOrAnsweringPutsTheQuestionSignDownAndTheNextTurnIsOrdinary() {
        let clicked = harness()
        finish(clicked, asking: "现在安装吗？")
        clicked.run(to: 20_000)
        #expect(clicked.router.dismissCompletion(now: clicked.now))
        clicked.run(to: 30_000)
        #expect(clicked.router.handoffQuestionSession == nil && clicked.router.displayed == .idle)

        let answered = harness()
        finish(answered, asking: "现在安装吗？")
        answered.run(to: 20_000)
        #expect(answered.router.handoffQuestionSession == answered.session)
        finish(answered, asking: nil)                 // the reply starts a new turn, which ends normally
        answered.run(to: 80_000)
        #expect(answered.router.handoffQuestionSession == nil)
        #expect(answered.router.completedSession == answered.session)
    }

    /// A chat waiting on an answer outranks one that merely finished.
    @Test func theQuestionIsShownBeforeAnotherChatsDoneSign() {
        let h = harness()
        for (id, question) in [("done", nil as String?), ("asked", "选哪个方案？")] {
            h.send(.taskStart, session: id)
            h.send(.finalAnswer, session: id)
            h.router.ingest(PetEvent(ts: h.now, source: "test", session: id, kind: .taskEnd,
                                     activity: question == nil ? nil : .question_for_user, detail: question), now: h.now)
        }
        h.run(to: 6000)
        #expect(h.router.handoffQuestionSession == "asked")
        #expect(h.router.sessionSummaries(now: h.now).filter(\.raisedSign).count == 2)
        #expect(h.router.dismissCompletion(now: h.now))
        h.run(to: 12_000)
        #expect(h.router.completedSession == "done")
    }
}
