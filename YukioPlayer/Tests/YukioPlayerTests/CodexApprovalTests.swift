import AppKit
import Testing
import YukioCore
@testable import YukioPlayer

@Suite struct CodexApprovalTests {
    func snapshot(_ method: String = "item/commandExecution/requestApproval", id: Any = 42) -> [String: Any] {
        ["id": "session", "turns": [["turnId": "turn", "status": "inProgress", "items": []]],
         "requests": [["id": id, "method": method, "params": ["threadId": "session", "turnId": "turn",
            "itemId": "tool", "reason": "Write the report?", "command": "echo report", "cwd": "/tmp",
            "permissions": ["network": ["enabled": true]]]]]]
    }
    @Test func decisionsUseExactRequestAndNeverSendChatText() throws {
        for method in CodexApprovals.methods.keys {
            let snap = snapshot(method)
            let p = try #require(CodexApprovals.pending(snap, session: "session").first)
            #expect(p.question.options.count == 2)
            for (i, decision) in ["accept", "decline"].enumerated() {
                let s = try CodexAnswerClient.submission(snapshot: snap, session: "session", callID: p.callID,
                                                        question: p.question, answer: p.question.options[i].label)
                #expect(s.method == CodexApprovals.methods[method])
                #expect(s.params["requestId"] as? Int == 42)
                #expect(s.params["input"] == nil)
                if method == "item/permissions/requestApproval" {
                    let response = try #require(s.params["response"] as? [String: Any])
                    #expect(response["scope"] as? String == "turn")
                    #expect((response["permissions"] as? [String: Any])?.isEmpty == (i == 1))
                } else { #expect(s.params["decision"] as? String == decision) }
            }
        }
    }
    @Test func staleChangedAmbiguousAndFreeTextCannotApprove() throws {
        let snap = snapshot()
        let p = try #require(CodexApprovals.pending(snap, session: "session").first)
        var gone = snap; gone["requests"] = [] as [[String: Any]]
        var changed = snapshot(); var requests = changed["requests"] as! [[String: Any]]
        var params = requests[0]["params"] as! [String: Any]; params["command"] = "other action"
        requests[0]["params"] = params; changed["requests"] = requests
        var duplicate = snap; duplicate["requests"] = (snap["requests"] as! [[String: Any]]) + (snap["requests"] as! [[String: Any]])
        var ended = snap; ended["turns"] = [["turnId": "turn", "status": "completed"]]
        var otherTurn = snap; otherTurn["turns"] = [["turnId": "next", "status": "inProgress"]]
        for stale in [gone, changed, duplicate, ended, otherTurn, snapshot(id: "42")] {
            #expect(throws: (any Error).self) {
                try CodexAnswerClient.submission(snapshot: stale, session: "session", callID: p.callID,
                    question: p.question, answer: p.question.options[0].label)
            }
        }
        #expect(throws: (any Error).self) {
            try CodexAnswerClient.submission(snapshot: snap, session: "other", callID: p.callID, question: p.question, answer: p.question.options[0].label)
        }
        #expect(throws: (any Error).self) {
            try CodexAnswerClient.submission(snapshot: snap, session: "session", callID: p.callID, question: p.question, answer: "yes")
        }
    }
    @Test func onlySupportedDecisionsShownAndCanonicalHistoryUsed() throws {
        var snap = snapshot()
        var requests = snap["requests"] as! [[String: Any]]
        var params = requests[0]["params"] as! [String: Any]
        params["availableDecisions"] = ["decline", "acceptForSession"]
        requests[0]["params"] = params; snap["requests"] = requests
        snap["turnHistory"] = ["kind": "canonical", "history": [
            "entitiesByKey": ["live": (snap["turns"] as! [[String: Any]])[0]],
            "islands": [["entries": [["value": "live"]]]]]]
        snap["turns"] = [] as [[String: Any]]
        let p = try #require(CodexApprovals.pending(snap, session: "session").first)
        #expect(p.question.options.count == 1)
        let s = try CodexAnswerClient.submission(snapshot: snap, session: "session", callID: p.callID, question: p.question, answer: p.question.options[0].label)
        #expect(s.params["decision"] as? String == "decline")
    }
    @Test @MainActor func approvalUsesSameCardWithoutTextInputOrDefaultSubmission() throws {
        let p = try #require(CodexApprovals.pending(snapshot(), session: "session").first)
        let layout = QuestionCardLayout(p.question)
        #expect(!layout.allowsText)
        if let path = ProcessInfo.processInfo.environment["YUKIO_APPROVAL_SNAPSHOT"] {
            let ctx = try #require(CGContext(data: nil, width: Int(layout.size.width * 2), height: Int(layout.size.height * 2),
                bitsPerComponent: 8, bytesPerRow: 0, space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue))
            ctx.scaleBy(x: 2, y: 2)
            NSGraphicsContext.current = NSGraphicsContext(cgContext: ctx, flipped: false)
            layout.draw(in: NSRect(origin: .zero, size: layout.size))
            NSGraphicsContext.current = nil
            let image = try #require(ctx.makeImage())
            let data = try #require(NSBitmapImageRep(cgImage: image).representation(using: .png, properties: [:]))
            try data.write(to: URL(fileURLWithPath: path))
        }
        let view = QuestionCardView(frame: NSRect(origin: .zero, size: layout.size)); view.card = layout
        #expect(view.field.isHidden)
        let bounds = NSRect(origin: .zero, size: layout.size)
        let hits = QuestionCardLayout.probePoints(layout, in: bounds).compactMap { layout.hit(at: $0.1, in: bounds) }
        #expect(!hits.contains(.input)); #expect(!hits.contains(.send))
        #expect(hits.contains(.option(0))); #expect(hits.contains(.close))
        let router = ActivityRouter(now: 0)
        router.ingest(PetEvent(ts: 1, source: "codex", session: "session", kind: .activityStart,
            eventID: p.callID, activity: .question_for_user, question: p.question), now: 1)
        router.tick(now: 100)
        router.tick(now: 1000)
        #expect(router.askingQuestion?.callID == p.callID)
        router.ingest(PetEvent(ts: 1001, source: "codex", session: "session", kind: .activityEnd, eventID: p.callID), now: 1001)
        router.tick(now: 2000)
        #expect(router.askingQuestion == nil)
    }
}
