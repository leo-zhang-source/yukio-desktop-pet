import Foundation
import YukioCore

/// Approval requests live in desktop snapshots, not in the model's tool-call log.
enum CodexApprovals {
    static let prefix = "yukio-approval:"
    static let methods = [
        "item/commandExecution/requestApproval": "thread-follower-command-approval-decision",
        "item/fileChange/requestApproval": "thread-follower-file-approval-decision",
        "item/permissions/requestApproval": "thread-follower-permissions-request-approval-response"
    ]
    struct Pending {
        let callID: String
        let question: PetQuestion
        let request: [String: Any]
    }
    static func pending(_ snapshot: [String: Any], session: String) throws -> [Pending] {
        guard snapshot["id"] as? String == session else { throw CodexAnswerClient.Failure.protocolMismatch }
        let turns = try CodexAnswerClient.turns(in: snapshot)
        guard let turn = turns.last, turn["status"] as? String == "inProgress", let turnID = (turn["turnId"] ?? turn["id"]) as? String else { return [] }
        return try (snapshot["requests"] as? [[String: Any]] ?? []).compactMap { request in
            guard let method = request["method"] as? String, methods[method] != nil,
                  let id = request["id"], id is String || id is Int,
                  request["completed"] as? Bool != true,
                  let params = request["params"] as? [String: Any],
                  params["threadId"] as? String == session, params["turnId"] as? String == turnID else { return nil }
            let fingerprint = String(data: try JSONSerialization.data(withJSONObject: request, options: [.sortedKeys]), encoding: .utf8)!
            let identity = String(data: try JSONSerialization.data(withJSONObject: [turnID, id], options: [.sortedKeys]), encoding: .utf8)!
            var lines = [params["reason"] as? String ?? tr("Approve this action?", "是否批准此操作？")]
            if let command = params["command"] as? String { lines.append(command) }
            if let cwd = params["cwd"] as? String { lines.append(tr("Folder: ", "目录：") + cwd) }
            if let root = params["grantRoot"] as? String { lines.append(tr("Path: ", "路径：") + root) }
            if method == "item/fileChange/requestApproval", let itemID = params["itemId"] as? String,
               let items = turn["items"] as? [[String: Any]],
               let item = items.first(where: { $0["id"] as? String == itemID }),
               let changes = item["changes"] as? [[String: Any]] {
                lines += changes.compactMap { $0["path"] as? String }
            }
            if let permissions = params["permissions"] as? [String: Any] {
                lines.append(String(data: try JSONSerialization.data(withJSONObject: permissions, options: [.sortedKeys]), encoding: .utf8)!)
            }
            let available = params["availableDecisions"] as? [Any]
            let canAccept = available == nil || available!.contains { $0 as? String == "accept" }
            let canDecline = available == nil || available!.contains { $0 as? String == "decline" }
            var options: [PetQuestion.Option] = []
            if canAccept { options.append(.init(label: tr("Approve once", "批准本次"))) }
            if canDecline { options.append(.init(label: tr("Decline", "拒绝"))) }
            let q = PetQuestion(header: tr("Needs your approval", "等你批准"), text: lines.joined(separator: "\n"),
                                options: options, approval: fingerprint)
            return Pending(callID: prefix + identity, question: q, request: request)
        }
    }

    static func submission(snapshot: [String: Any], session: String, callID: String,
                           question: PetQuestion, answer: String) throws -> (method: String, params: [String: Any]) {
        let matches = try pending(snapshot, session: session).filter { $0.callID == callID && $0.question == question }
        guard matches.count == 1, let match = matches.first,
              question.options.contains(where: { $0.label == answer }),
              let method = match.request["method"] as? String, let target = methods[method],
              let id = match.request["id"] else { throw CodexAnswerClient.Failure.expired }
        let approve = answer == tr("Approve once", "批准本次")
        var result: [String: Any] = ["conversationId": session, "requestId": id]
        if method == "item/permissions/requestApproval" {
            let params = match.request["params"] as? [String: Any] ?? [:]
            guard let permissions = params["permissions"] as? [String: Any] else { throw CodexAnswerClient.Failure.protocolMismatch }
            result["response"] = ["permissions": approve ? permissions : [:], "scope": "turn"]
        } else { result["decision"] = approve ? "accept" : "decline" }
        return (target, result)
    }
}

/// UI-thread state; network work happens on a background queue one session at a time.
final class CodexApprovalMonitor {
    private var shown: [String: Set<String>] = [:]
    private var cursor = 0
    private var busy = false
    private var nextPoll: Double = 0

    func poll(sessions: [String], now: Double, receive: @escaping ([PetEvent]) -> Void) {
        shown = shown.filter { sessions.contains($0.key) }
        guard !busy, now >= nextPoll, !sessions.isEmpty else { return }
        let session = sessions[cursor % sessions.count]
        cursor += 1; busy = true; nextPoll = now + 750
        DispatchQueue.global(qos: .utility).async {
            let result = Result { try CodexAnswerClient().approvalSnapshot(session: session) }
            DispatchQueue.main.async {
                self.busy = false
                guard case .success(let snapshot) = result,
                      let pending = try? CodexApprovals.pending(snapshot, session: session) else { return }
                let timestamp = now // Reject late responses if a newer task has already started.
                let old = self.shown[session] ?? []
                let current = Set(pending.map(\.callID))
                var events = old.subtracting(current).sorted().map {
                    PetEvent(ts: timestamp, source: "codex", session: session, kind: .activityEnd, eventID: $0)
                }
                for p in pending {
                    events.append(PetEvent(ts: timestamp, source: "codex", session: session, kind: .activityStart,
                        eventID: p.callID, activity: .question_for_user, detail: p.question.shortLabel, question: p.question))
                }
                self.shown[session] = current
                receive(events)
            }
        }
    }
}
