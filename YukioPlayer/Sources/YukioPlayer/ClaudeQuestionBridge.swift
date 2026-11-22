import Foundation
import Darwin
import YukioCore

/// Explicit AskUserQuestion hook. Answers stay local; only this tool's input is updated.
final class ClaudeQuestionBridge {
    struct Request: Codable {
        var provider: String? = nil
        let id: String
        let session: String
        let callID: String
        let questions: [PetQuestion]
        let pid: Int32
        let createdAt: Double
        let expiresAt: Double
    }
    enum Failure: LocalizedError {
        case notConnected, expired, unconfirmed
        var errorDescription: String? {
            switch self {
            case .notConnected: return tr("Claude bridge needed · ask again after setup", "Claude 需连接回答通道后重新提问")
            case .expired: return tr("Question expired or already answered", "问题已结束或已回答")
            case .unconfirmed: return tr("No receipt yet · retry to check", "暂未收到回执 · 可重试核对")
            }
        }
    }
    static var defaultRoot: URL {
        if let path = ProcessInfo.processInfo.environment["YUKIO_ANSWER_BRIDGE_DIR"] { return URL(fileURLWithPath: path) }
        return FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/YukioPlayer/answers")
    }
    let root: URL
    private var shown: [String: Request] = [:]
    private var heartbeatAt: Double = 0
    init(root: URL = defaultRoot) { self.root = root }
    private func prepare() throws {
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
    }
    private func request(at dir: URL, now: Double) -> Request? {
        guard !FileManager.default.fileExists(atPath: dir.appendingPathComponent("done").path) else { return nil }
        let file = dir.appendingPathComponent("request.json")
        guard let info = try? file.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey]),
              info.isRegularFile == true, info.isSymbolicLink != true, (info.fileSize ?? Int.max) < 1 << 20,
              let bytes = try? Data(contentsOf: file), bytes.count < 1 << 20,
              let value = try? JSONDecoder().decode(Request.self, from: bytes), value.id == dir.lastPathComponent,
              !value.session.isEmpty, value.session.count <= 256, !value.callID.isEmpty, value.callID.count <= 256,
              (1...64).contains(value.questions.count), value.pid > 0,
              value.createdAt.isFinite, value.createdAt > 0, value.createdAt <= now + 1000,
              value.expiresAt.isFinite, value.expiresAt > now, kill(value.pid, 0) == 0,
              !FileManager.default.fileExists(atPath: dir.appendingPathComponent("done").path) else { return nil }
        return value
    }
    private func source(_ r: Request) -> String { r.provider == "deepseek" ? DeepCodeMessageParser.source : ClaudeTranscriptParser.source }
    private func key(_ r: Request, _ index: Int) -> String { "yukio-\(r.provider ?? "claude"):\(r.id):\(index)" }
    func poll(now: Double, enabled: Bool = true, providers: Set<String> = ["claude", "deepseek"],
              acceptsClaudeSession: (String) -> Bool = { _ in true }) -> [PetEvent] {
        try? prepare()
        if enabled && now - heartbeatAt > 1000 {
            for provider in providers.intersection(["claude", "deepseek"]) {
                try? Data(String(getpid()).utf8).write(to: root.appendingPathComponent(provider == "claude" ? "listener" : "listener-deepseek"), options: .atomic)
            }
            heartbeatAt = now
        }
        var next: [String: Request] = [:], events: [PetEvent] = []
        if enabled {
            let directories = (try? FileManager.default.contentsOfDirectory(at: root, includingPropertiesForKeys: nil)) ?? []
            for dir in directories where UUID(uuidString: dir.lastPathComponent) != nil {
                guard let r = request(at: dir, now: now), providers.contains(r.provider ?? "claude"),
                      r.provider == "deepseek" || acceptsClaudeSession(r.session),
                      let index = r.questions.indices.first(where: { !FileManager.default.fileExists(atPath: dir.appendingPathComponent("receipt-\($0).json").path) }) else { continue }
                let id = key(r, index)
                next[id] = r
                if shown[id] == nil {
                    events.append(PetEvent(ts: r.createdAt, source: source(r), session: r.session,
                        kind: .activityStart, eventID: id, activity: .question_for_user,
                        tool: r.questions[index].isApproval ? "PermissionRequest" : "AskUserQuestion", detail: r.questions[index].shortLabel,
                        question: r.questions[index], relatedCallID: r.callID))
                }
            }
        }
        for (id, r) in shown where next[id] == nil {
            events.append(PetEvent(ts: now, source: source(r), session: r.session, kind: .activityEnd, eventID: id))
            // A receipt for every item proves the hook has the complete answer.
            // Retire the transcript's copy too, before it can flash back while
            // Claude is still writing the corresponding tool_result.
            let dir = root.appendingPathComponent(r.id)
            if r.questions.indices.allSatisfy({ FileManager.default.fileExists(atPath: dir.appendingPathComponent("receipt-\($0).json").path) }) {
                events.append(PetEvent(ts: now, source: source(r), session: r.session,
                    kind: .activityEnd, eventID: r.callID, relatedCallID: r.callID))
            }
        }
        shown = next
        return events
    }
    func send(session: String, callID: String, answer: String, provider: String = "claude") throws {
        let parts = callID.split(separator: ":")
        guard parts.count == 3, parts[0] == "yukio-\(provider)", UUID(uuidString: String(parts[1])) != nil,
              let index = Int(parts[2]), index >= 0 else { throw Failure.notConnected }
        let dir = root.appendingPathComponent(String(parts[1]))
        guard !answer.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty, answer.utf8.count < 65536,
              let requestData = try? Data(contentsOf: dir.appendingPathComponent("request.json")),
              let savedRequest = try? JSONDecoder().decode(Request.self, from: requestData),
              savedRequest.id == String(parts[1]), savedRequest.session == session,
              (savedRequest.provider ?? "claude") == provider, index < savedRequest.questions.count else { throw Failure.expired }
        if savedRequest.questions[index].isApproval && !ApprovalQuestion.accepts(answer) { throw Failure.expired }
        let receipt = dir.appendingPathComponent("receipt-\(index).json")
        if let data = try? Data(contentsOf: receipt), let saved = try? JSONDecoder().decode(String.self, from: data) {
            guard saved == answer else { throw Failure.expired }
            return
        }
        guard let r = request(at: dir, now: Date().timeIntervalSince1970 * 1000), r.session == session, (r.provider ?? "claude") == provider,
              index < r.questions.count else { throw Failure.expired }
        let response = dir.appendingPathComponent("answer-\(index).json")
        if let data = try? Data(contentsOf: response), let saved = try? JSONDecoder().decode(String.self, from: data), saved != answer {
            throw Failure.unconfirmed // Do not overwrite an answer that may already be in flight.
        }
        try JSONEncoder().encode(answer).write(to: response, options: .atomic)
        let deadline = Date().addingTimeInterval(3)
        while Date() < deadline {
            if let data = try? Data(contentsOf: receipt), let saved = try? JSONDecoder().decode(String.self, from: data), saved == answer { return }
            Thread.sleep(forTimeInterval: 0.05)
        }
        throw Failure.unconfirmed
    }

    /// PermissionRequest lacks tool_use_id. Correlate only a single unresolved
    /// call with exactly matching tool/input in the client-provided transcript.
    /// No title/time/proximity matching; ambiguous or unavailable records fail closed.
    static func transcriptCallID(_ obj: [String: Any]) -> String? {
        guard let path = obj["transcript_path"] as? String, let session = obj["session_id"] as? String,
              let name = obj["tool_name"] as? String, let input = obj["tool_input"] as? [String: Any],
              let expected = try? JSONSerialization.data(withJSONObject: input, options: [.sortedKeys]),
              let attrs = try? FileManager.default.attributesOfItem(atPath: path), attrs[.type] as? FileAttributeType == .typeRegular,
              let size = attrs[.size] as? UInt64,
              let handle = try? FileHandle(forReadingFrom: URL(fileURLWithPath: path)) else { return nil }
        defer { try? handle.close() }
        let offset = size > 1 << 20 ? size - (1 << 20) : 0
        do {
            try handle.seek(toOffset: offset)
            guard var data = try handle.read(upToCount: 1 << 20) else { return nil }
            if offset > 0 {
                guard let newline = data.firstIndex(of: 10) else { return nil }
                data = data.subdata(in: data.index(after: newline)..<data.endIndex)
            }
            var stream = JSONObjectStream(), matches: Set<String> = []
            for bytes in stream.append(data) {
                guard let row = (try? JSONSerialization.jsonObject(with: bytes)) as? [String: Any], row["sessionId"] as? String == session,
                      row["isSidechain"] as? Bool != true, row["agentId"] == nil,
                      row["isMeta"] as? Bool != true, row["isCompactSummary"] as? Bool != true,
                      let message = row["message"] as? [String: Any] else { continue }
                let blocks = message["content"] as? [[String: Any]] ?? []
                if row["type"] as? String == "user" {
                    let results = blocks.filter { $0["type"] as? String == "tool_result" }
                    for result in results { if let id = result["tool_use_id"] as? String { matches.remove(id) } }
                    if results.isEmpty, row["promptSource"] as? String != "system" { matches.removeAll() }
                } else if row["type"] as? String == "assistant" {
                    for block in blocks where block["type"] as? String == "tool_use" && block["name"] as? String == name {
                        guard let id = block["id"] as? String, !id.isEmpty, id.count <= 256,
                              let value = block["input"] as? [String: Any],
                              let encoded = try? JSONSerialization.data(withJSONObject: value, options: [.sortedKeys]), encoded == expected else { continue }
                        matches.insert(id)
                    }
                }
            }
            return matches.count == 1 ? matches.first : nil
        } catch { return nil }
    }

    static func priorAnswers(root: URL, request: Request) -> [Int: Data] {
        var result: [Int: Data] = [:]
        let paths = ((try? FileManager.default.contentsOfDirectory(at: root, includingPropertiesForKeys: [.contentModificationDateKey])) ?? []).sorted {
            ((try? $0.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast)
                > ((try? $1.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast)
        }
        for path in paths.prefix(512) where UUID(uuidString: path.lastPathComponent) != nil && path.lastPathComponent != request.id {
            guard let info = try? path.resourceValues(forKeys: [.isSymbolicLinkKey]), info.isSymbolicLink != true,
                  let data = try? Data(contentsOf: path.appendingPathComponent("request.json")), data.count <= 1 << 20,
                  let old = try? JSONDecoder().decode(Request.self, from: data), old.id == path.lastPathComponent,
                  (old.provider ?? "claude") == (request.provider ?? "claude"), old.session == request.session, old.callID == request.callID,
                  old.createdAt < request.createdAt, old.questions == request.questions else { continue }
            for index in request.questions.indices {
                guard let receipt = try? Data(contentsOf: path.appendingPathComponent("receipt-\(index).json")), receipt.count < 65536,
                      let answer = try? JSONDecoder().decode(String.self, from: receipt), !answer.isEmpty else { continue }
                // Conflicting receipts must not choose an answer on the user's behalf.
                if let previous = result[index], previous != receipt { return [:] }
                result[index] = receipt
            }
        }
        return result
    }

    /// Called by the explicitly configured Claude question / permission hooks.
    static func runHook(input: Data, root: URL = defaultRoot, waitSeconds: Double = 570) -> Data {
        let empty = Data("{}".utf8)
        guard let obj = try? JSONSerialization.jsonObject(with: input) as? [String: Any],
              let session = obj["session_id"] as? String,
              let toolInput = obj["tool_input"] as? [String: Any],
              let toolName = obj["tool_name"] as? String,
              (obj["hook_event_name"] as? String == "PermissionRequest" ||
               (obj["hook_event_name"] as? String == "PreToolUse" && toolName == "AskUserQuestion")),
              let attributes = try? FileManager.default.attributesOfItem(atPath: root.appendingPathComponent("listener").path),
              let modified = attributes[.modificationDate] as? Date, Date().timeIntervalSince(modified) < 4,
              let listenerText = try? String(contentsOf: root.appendingPathComponent("listener")),
              let listenerPID = Int32(listenerText), kill(listenerPID, 0) == 0 else { return empty }
        let permissionHook = obj["hook_event_name"] as? String == "PermissionRequest"
        // Claude routes AskUserQuestion through its permission callback too.
        // That callback asks for the answers, not permission to ask a question.
        let isApproval = permissionHook && toolName != "AskUserQuestion"
        let callID = obj["tool_use_id"] as? String ?? transcriptCallID(obj) ?? UUID().uuidString
        let raw: [[String: Any]]
        let questions: [PetQuestion]
        if isApproval {
            guard let data = try? JSONSerialization.data(withJSONObject: toolInput, options: [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]), data.count < 60000 else { return empty }
            let text = "Claude 申请使用：\(toolName)\n工作位置：\(obj["cwd"] as? String ?? "未提供")\n\n" + String(decoding: data, as: UTF8.self)
            let q = ApprovalQuestion.make(provider: "Claude", details: text)
            questions = [q]; raw = [["question": text]]
        } else {
            raw = toolInput["questions"] as? [[String: Any]] ?? []
            questions = raw.compactMap { PetQuestion.from(input: $0) }
        }
        guard (1...64).contains(raw.count), questions.count == raw.count, Set(raw.compactMap { $0["question"] as? String }).count == raw.count else { return empty }
        let now = Date().timeIntervalSince1970 * 1000
        let parentPID = getppid()
        let r = Request(id: UUID().uuidString, session: session, callID: callID, questions: questions,
                        pid: getpid(), createdAt: now, expiresAt: now + waitSeconds * 1000)
        let dir = root.appendingPathComponent(r.id)
        do {
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
            defer { try? Data().write(to: dir.appendingPathComponent("done"), options: .atomic) }
            var answers: [String: String] = [:]
            if !isApproval {
                for (index, receipt) in priorAnswers(root: root, request: r) {
                    if let question = raw[index]["question"] as? String,
                       let answer = try? JSONDecoder().decode(String.self, from: receipt) {
                        answers[question] = answer
                        try receipt.write(to: dir.appendingPathComponent("receipt-\(index).json"), options: .atomic)
                    }
                }
            }
            // Publish the lease after inherited receipts, so a resumed second
            // question cannot briefly expose the already answered first one.
            try JSONEncoder().encode(r).write(to: dir.appendingPathComponent("request.json"), options: .atomic)
            let deadline = Date().addingTimeInterval(waitSeconds)
            while Date() < deadline {
                guard let attrs = try? FileManager.default.attributesOfItem(atPath: root.appendingPathComponent("listener").path),
                      let alive = attrs[.modificationDate] as? Date, Date().timeIntervalSince(alive) < 5,
                      kill(listenerPID, 0) == 0, parentPID > 1, kill(parentPID, 0) == 0 else { return empty }
                for index in raw.indices where answers[raw[index]["question"] as? String ?? ""] == nil {
                    guard let text = raw[index]["question"] as? String,
                          let data = try? Data(contentsOf: dir.appendingPathComponent("answer-\(index).json")), data.count < 65536,
                          let answer = try? JSONDecoder().decode(String.self, from: data), !answer.isEmpty else { continue }
                    if isApproval && !ApprovalQuestion.accepts(answer) { continue }
                    answers[text] = answer
                    try data.write(to: dir.appendingPathComponent("receipt-\(index).json"), options: .atomic)
                }
                if answers.count == raw.count {
                    if isApproval {
                        let allow = answers.values.first == ApprovalQuestion.allow
                        let decision: [String: Any] = allow
                            ? ["behavior": "allow", "updatedInput": toolInput]
                            : ["behavior": "deny", "message": "The user declined this operation in Yukio."]
                        return try JSONSerialization.data(withJSONObject: ["hookSpecificOutput": [
                            "hookEventName": "PermissionRequest", "decision": decision]])
                    }
                    var updated = toolInput
                    updated["answers"] = answers
                    if permissionHook {
                        return try JSONSerialization.data(withJSONObject: ["hookSpecificOutput": [
                            "hookEventName": "PermissionRequest", "decision": ["behavior": "allow", "updatedInput": updated]]])
                    }
                    return try JSONSerialization.data(withJSONObject: ["hookSpecificOutput": ["hookEventName": "PreToolUse",
                        "permissionDecision": "allow", "updatedInput": updated]])
                }
                Thread.sleep(forTimeInterval: 0.1)
            }
            return empty
        } catch { return empty }
    }
}
