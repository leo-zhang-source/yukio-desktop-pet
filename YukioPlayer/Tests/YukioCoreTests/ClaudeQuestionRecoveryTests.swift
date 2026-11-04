import Foundation
import Testing
@testable import YukioCore

@Suite(.serialized) struct ClaudeQuestionRecoveryTests {
    private func question(_ f: LiveSourceTests, _ t: Double, session: String = "B", id: String = "q") -> String {
        #"{"type":"assistant","sessionId":"\#(session)","timestamp":"\#(f.stamp(t))","message":{"stop_reason":"tool_use","content":[{"type":"tool_use","id":"\#(id)","name":"AskUserQuestion","input":{"questions":[{"question":"RED or BLUE?","options":[{"label":"RED"},{"label":"BLUE"}]}]}}]}}"# + "\n"
    }
    private func result(_ f: LiveSourceTests, _ t: Double, id: String = "q") -> String {
        #"{"type":"user","sessionId":"B","timestamp":"\#(f.stamp(t))","message":{"content":[{"type":"tool_result","tool_use_id":"\#(id)","content":"RED"}]}}"# + "\n"
    }
    private func oldFile(_ f: LiveSourceTests, text: String) throws -> URL {
        let url = f.project.appendingPathComponent("B.jsonl")
        try Data(text.utf8).write(to: url)
        try FileManager.default.setAttributes([.modificationDate: Date(timeIntervalSinceNow: -3600)], ofItemAtPath: url.path)
        return url
    }
    private func source(_ f: LiveSourceTests) -> ClaudeTranscriptSource {
        ClaudeTranscriptSource(projectsDir: f.root.appendingPathComponent("projects"))
    }

    @Test func oldUnansweredQuestionRestoresWithoutOldWorkAndReceivesOnlyItsAnswer() throws {
        let f = try LiveSourceTests(); defer { try? FileManager.default.removeItem(at: f.root) }
        let t = f.now() - 3_600_000
        let url = try oldFile(f, text: f.userLine("B", t) + f.toolLine("B", t+1, id: "work", command: "sleep 999") + question(f, t+2))
        let src = source(f), router = ActivityRouter(now: f.now())
        let events = src.poll(now: f.now())
        #expect(events.map(\.kind) == [.taskStart, .activityStart])
        #expect(events.last?.eventID == "q" && events.last?.ts == PetEvent.parseTimestamp(f.stamp(t+2)))
        for event in events { router.ingest(event, now: event.ts) }
        #expect(router.desiredState(now: f.now()) == .question_for_user)
        #expect(router.sessions["B"]?.open.map(\.id) == ["q"])
        #expect(src.poll(now: f.now()+100).isEmpty)
        try f.append(url, result(f, f.now()))
        let receipt = src.poll(now: f.now()+200)
        #expect(receipt.count == 1 && receipt.first?.eventID == "q")
        for event in receipt { router.ingest(event, now: event.ts) }
        #expect(router.sessions["B"]?.open.isEmpty == true)
    }

    @Test func answeredCancelledEndedAndNewTurnDoNotRestoreAnOldQuestion() throws {
        let f = try LiveSourceTests(); defer { try? FileManager.default.removeItem(at: f.root) }
        let t = f.now()-3_600_000
        let endings = [result(f,t+2), f.userLine("B",t+2),
            #"{"type":"user","sessionId":"B","timestamp":"\#(f.stamp(t+2))","message":{"content":"[Request interrupted by user]"}}"# + "\n",
            #"{"type":"assistant","sessionId":"B","timestamp":"\#(f.stamp(t+2))","message":{"stop_reason":"end_turn","content":[{"type":"text","text":"done"}]}}"# + "\n"]
        for ending in endings {
            _ = try oldFile(f, text: f.userLine("B",t)+question(f,t+1)+ending)
            #expect(source(f).poll(now:f.now()).isEmpty)
        }
    }

    @Test func missingTurnBoundaryTruncatedTailAndPartialReceiptAreNotRecovered() throws {
        let f = try LiveSourceTests(); defer { try? FileManager.default.removeItem(at: f.root) }
        let t=f.now()-3_600_000
        _ = try oldFile(f,text:question(f,t))
        #expect(source(f).poll(now:f.now()).isEmpty)
        _ = try oldFile(f,text:f.userLine("B",t)+String(repeating:" ",count:1500)+"\n"+question(f,t+1))
        let bounded=source(f); bounded.bootstrapTailBytes=800
        #expect(bounded.poll(now:f.now()).isEmpty)
        _ = try oldFile(f,text:f.userLine("B",t)+question(f,t+1)+String(result(f,t+2).dropLast(5)))
        #expect(source(f).poll(now:f.now()).isEmpty)
    }

    @Test func ambiguousReceiptAndForeignSessionAreNotRecovered() throws {
        let f=try LiveSourceTests(); defer { try? FileManager.default.removeItem(atPath:f.root.path) }
        let t=f.now()-3_600_000
        _ = try oldFile(f,text:f.userLine("B",t)+question(f,t+1)+result(f,t+2,id:""))
        #expect(source(f).poll(now:f.now()).isEmpty)
        _ = try oldFile(f,text:f.userLine("B",t)+question(f,t+1,session:"A"))
        #expect(source(f).poll(now:f.now()).isEmpty)
    }

    @Test func deletingRestoredSourceClearsOnlyItsQuestion() throws {
        let f=try LiveSourceTests(); defer { try? FileManager.default.removeItem(at:f.root) }
        let t=f.now()-3_600_000
        let url=try oldFile(f,text:f.userLine("B",t)+question(f,t+1))
        let src=source(f), router=ActivityRouter(now:f.now())
        for e in src.poll(now:f.now()) { router.ingest(e,now:e.ts) }
        router.ingest(PetEvent(ts:t,source:"codex",session:"A",kind:.activityStart,eventID:"a",activity:.question_for_user,question:PetQuestion(text:"Other?")),now:t)
        try FileManager.default.removeItem(at:url)
        for e in src.poll(now:f.now()+200) { router.ingest(e,now:e.ts) }
        #expect(router.sessions["B"]?.taskActive == false)
        #expect(router.sessions["A"]?.open.count == 1)
    }

    @Test func explicitQuestionOutlivesToolTimeoutButOrdinaryWorkDoesNot() {
        var config=RouterConfig(); config.staleOpenToolMs=1000
        let router=ActivityRouter(config:config,now:0)
        router.ingest(PetEvent(ts:0,source:"claude-transcript",session:"B",kind:.activityStart,eventID:"q",activity:.question_for_user,question:PetQuestion(text:"Choose?")),now:0)
        router.ingest(PetEvent(ts:0,source:"claude-transcript",session:"A",kind:.activityStart,eventID:"work",activity:.verify),now:0)
        #expect(router.desiredState(now:3_600_000) == .question_for_user)
        #expect(router.sessions["A"].map { router.isLive($0,now:3_600_000) } == false)
        router.ingest(PetEvent(ts:3_600_001,source:"claude-transcript",session:"B",kind:.taskAbort),now:3_600_001)
        #expect(router.desiredState(now:3_600_002) == .idle)
    }

    @Test func sourceLossAndNewTurnRetireLongWaitWithoutCompletionSign() {
        let router=ActivityRouter(now:0)
        for id in ["A","B"] {
            router.ingest(PetEvent(ts:0,source:"claude-transcript",session:id,kind:.activityStart,eventID:"q",activity:.question_for_user,question:PetQuestion(text:id)),now:0)
        }
        router.ingest(PetEvent(ts:3_600_000,source:"claude-transcript",session:"A",kind:.taskStart),now:3_600_000)
        #expect(router.sessions["A"]?.open.isEmpty == true)
        #expect(router.sessions["B"]?.open.count == 1)
        router.ingest(PetEvent(ts:3_600_100,source:"claude-transcript",session:"",kind:.sourceLost),now:3_600_100)
        #expect(router.desiredState(now:3_600_200) == .idle)
        #expect(router.completedSession == nil)
    }
}
