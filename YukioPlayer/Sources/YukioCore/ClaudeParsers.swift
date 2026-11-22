import Foundation
import CoreFoundation

/// Claude Code 会话转录（~/.claude/projects/<项目>/<会话>.jsonl）→ 事件。
///
/// 这是 Claude Code 本地写入的会话记录，不是公开 API；字段可能随版本变化。
/// 解析只读取：条目类型、会话 ID、时间戳、会话标题、请求第一行、工具名与输入（用于分类和简短说明）、
/// 任务清单、工具结果 ID、结束原因。不保存、不上传任何对话内容。
public final class ClaudeTranscriptParser {
    public static let source = "claude-transcript"

    // A model stop reason ends a response, not necessarily the client's turn.
    // Keep only identities and lifecycle metadata; never retain response text.
    private final class Turn {
        var latestTimestamp: Double = -.infinity
        var promptID: String?
        var hookPromptID: String?
        var answerID: String?
        var answerTimestamp: Double = -.infinity
        var completedAnswerID: String?
        var responseID: String?
        var responseHasTools = false
        var answerEntrypoint: String?
        /// The turn's closing next-step box asked something the chat cannot continue without.
        var handoffQuestion: String?
        var background: [String: String] = [:]
        var backgroundLimited = false
        var stops: [String: (hasPendingWork: Bool, receivedAt: Double)] = [:]
        var pending: Bool { backgroundLimited || background.values.contains(promptID ?? "") }
    }
    private var turns: [String: Turn] = [:]

    private func turn(for session: String) -> Turn {
        if let turn = turns[session] { return turn }
        if turns.count >= 1024, let oldest = turns.min(by: { $0.value.latestTimestamp < $1.value.latestTimestamp }) {
            turns.removeValue(forKey: oldest.key)
        }
        let turn = Turn()
        turns[session] = turn
        return turn
    }

    /// Stop runs before other Stop hooks have decided whether work continues.
    /// It may veto completion using an exact prompt identity, but cannot prove it.
    func observeStopHook(_ obj: [String: Any], receivedAt: Double) -> [PetEvent] {
        guard obj["hook_event_name"] as? String == "Stop",
              let session = obj["session_id"] as? String, !session.isEmpty,
              let prompt = obj["prompt_id"] as? String, !prompt.isEmpty,
              obj["agent_id"] == nil, obj["isSidechain"] as? Bool != true else { return [] }
        let turn = turn(for: session)
        if let previous = turn.stops[prompt], receivedAt < previous.receivedAt { return [] }
        let owner = turn.hookPromptID == prompt ? (turn.promptID ?? prompt) : prompt
        // Missing/unknown registries do not certify that background work is gone.
        let tasks = obj["background_tasks"] as? [Any]
        let crons = obj["session_crons"] as? [Any]
        var pending = tasks == nil || crons == nil
        var active = Set<String>()
        for (items, prefix) in [(tasks, ""), (crons, "cron:")] {
            for item in items ?? [] {
                guard let row = item as? [String: Any], let id = row["id"] as? String,
                      !id.isEmpty, id.count <= 256 else { pending = true; continue }
                let key = prefix + id
                if let status = row["status"] as? String, ["completed", "failed", "killed", "cancelled"].contains(status) {
                    turn.background.removeValue(forKey: key); continue
                }
                active.insert(key)
                if turn.background[key] == nil {
                    if turn.background.count < 256 { turn.background[key] = owner }
                    else { turn.backgroundLimited = true }
                }
                if turn.background[key] == owner { pending = true }
            }
        }
        if tasks != nil, crons != nil {
            // A current registry can retire a job whose notification has not yet
            // reached the transcript. Earlier persistent services retain ownership.
            turn.background = turn.background.filter { $0.value != owner || active.contains($0.key) }
        }
        pending = pending || turn.backgroundLimited
        if turn.stops[prompt] == nil, turn.stops.count >= 16,
           let oldest = turn.stops.min(by: { $0.value.receivedAt < $1.value.receivedAt }) {
            turn.stops.removeValue(forKey: oldest.key)
        }
        turn.stops[prompt] = (pending, receivedAt)
        guard pending, turn.hookPromptID == prompt, receivedAt >= turn.latestTimestamp else { return [] }
        turn.answerID = nil
        return [PetEvent(ts: receivedAt, source: Self.source, session: session, kind: .thinking)]
    }

    public init() {}

    private static func ended(_ turn: Turn, at: Double, session: String) -> [PetEvent] {
        let question = turn.handoffQuestion; turn.handoffQuestion = nil
        return [PetEvent(ts: at, source: Self.source, session: session, kind: .finalAnswer),
                PetEvent(ts: at, source: Self.source, session: session, kind: .taskEnd,
                         activity: question == nil ? nil : .question_for_user, detail: question)]
    }

    /// Claude Desktop closes a turn with a "next step" box (`mcp__ccd_turn__wrap_up`): a recap,
    /// optionally one question with reply buttons, and `blocked: true` only when the work
    /// cannot go on until the user answers. That flag is the client's own distinction between
    /// a question and a next-step suggestion; the wording of the question is never interpreted.
    /// Internal client format: anything unrecognized stays an ordinary completed turn.
    static let nextStepTool = "mcp__ccd_turn__wrap_up"
    static func blockingQuestion(nextStep input: [String: Any]) -> String? {
        guard let flag = input["blocked"] as? NSNumber, CFGetTypeID(flag) == CFBooleanGetTypeID(), flag.boolValue,
              let ask = (input["ask"] as? String)?.split(whereSeparator: \.isWhitespace).joined(separator: " "),
              !ask.isEmpty else { return nil }
        return String(ask.prefix(200))
    }

    private func observeBackground(_ obj: [String: Any], turn: Turn) {
        guard let result = obj["toolUseResult"] as? [String: Any] else { return }
        if let id = result["backgroundTaskId"] as? String, !id.isEmpty, id.count <= 256 {
            if turn.background[id] != nil || turn.background.count < 256 { turn.background[id] = turn.promptID ?? "" }
            else { turn.backgroundLimited = true }
        }
        if let task = result["task"] as? [String: Any], let status = task["status"] as? String,
           ["completed", "failed", "killed", "cancelled"].contains(status),
           let id = (task["task_id"] ?? task["id"]) as? String { turn.background.removeValue(forKey: id) }
    }

    private func observeNotification(_ obj: [String: Any], text: String, turn: Turn) -> Bool {
        guard (obj["origin"] as? [String: Any])?["kind"] as? String == "task-notification",
              obj["promptSource"] as? String == "system" else { return false }
        let text = String(text.prefix(16000))
        func captures(_ pattern: String, in value: String) -> [String] {
            guard let regex = try? NSRegularExpression(pattern: pattern, options: [.dotMatchesLineSeparators]) else { return [] }
            return regex.matches(in: value, range: NSRange(value.startIndex..., in: value)).compactMap {
                Range($0.range(at: 1), in: value).map { String(value[$0]) }
            }
        }
        if let body = captures(#"^\s*<task-notification>(.*?)</task-notification>"#, in: text).first {
            let ids = captures(#"<task-id>([A-Za-z0-9_-]{1,256})</task-id>"#, in: body)
            let statuses = captures(#"<status>(completed|failed|killed|cancelled)</status>"#, in: body)
            if ids.count == 1, statuses.count == 1 { turn.background.removeValue(forKey: ids[0]) }
        }
        return true
    }

    public func events(fromLine data: Data) -> [PetEvent] {
        guard let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { return [] }
        return events(from: obj)
    }

    public func events(from obj: [String: Any]) -> [PetEvent] {
        guard let type = obj["type"] as? String,
              let session = obj["sessionId"] as? String, !session.isEmpty else { return [] }
        // 子代理（sidechain）的活动不驱动主角色。
        if obj["isSidechain"] as? Bool == true || obj["agentId"] != nil { return [] }
        // 会话标题（大任务）。这两类条目不带时间戳，用 0：只更新标题，不影响活动与失联判断。
        if type == "custom-title" || type == "ai-title" {
            guard let title = (obj["customTitle"] ?? obj["aiTitle"]) as? String else { return [] }
            return [PetEvent(ts: 0, source: Self.source, session: session, kind: .sessionTitle, detail: title)]
        }
        let turn = turn(for: session)
        if type == "last-prompt" {
            guard let answer = turn.answerID, obj["leafUuid"] as? String == answer,
                  turn.answerEntrypoint == "sdk-cli", !turn.pending else { return [] }
            turn.completedAnswerID = answer; turn.answerID = nil
            return Self.ended(turn, at: turn.answerTimestamp, session: session)
        }
        guard let ts = PetEvent.parseTimestamp(obj["timestamp"] as? String) else { return [] }
        guard ts >= turn.latestTimestamp else { return [] }

        func ev(_ kind: PetEvent.Kind, id: String? = nil, activity: PetState? = nil, tool: String? = nil,
                detail: String? = nil, todos: [TodoItem]? = nil, question: PetQuestion? = nil) -> PetEvent {
            PetEvent(ts: ts, source: Self.source, session: session, kind: kind, eventID: id, activity: activity,
                     tool: tool, detail: detail, todos: todos, question: question)
        }

        switch type {
        case "user":
            if obj["isMeta"] as? Bool == true || obj["isCompactSummary"] as? Bool == true { return [] }
            let message = obj["message"] as? [String: Any]
            if let role = message?["role"] as? String, role != "user" { return [] }
            let content = message?["content"]
            func promptEvents(_ text: String, hasOtherBlocks: Bool) -> [PetEvent] {
                if observeNotification(obj, text: text, turn: turn) {
                    turn.latestTimestamp = ts; turn.answerID = nil
                    turn.hookPromptID = obj["promptId"] as? String
                    return [ev(.thinking)]
                }
                guard let kind = userText(text, hasOtherBlocks: hasOtherBlocks) else { return [] }
                turn.latestTimestamp = ts
                turn.answerID = nil
                turn.promptID = (obj["promptId"] as? String) ?? (obj["uuid"] as? String) ?? "turn:\(ts)"
                turn.hookPromptID = turn.promptID
                turn.responseID = nil
                turn.responseHasTools = false
                turn.handoffQuestion = nil
                return [ev(kind, detail: Self.promptLine(text))]
            }
            if let blocks = content as? [[String: Any]] {
                let results = blocks.filter { $0["type"] as? String == "tool_result" }
                if !results.isEmpty {
                    turn.latestTimestamp = ts
                    turn.answerID = nil
                    observeBackground(obj, turn: turn)
                    var out = results.compactMap { (b: [String: Any]) -> PetEvent? in
                        guard let id = b["tool_use_id"] as? String else { return nil }
                        return ev(Self.isFailure(b) ? .activityFailed : .activityEnd, id: id)
                    }
                    // TaskCreate 新任务的编号只在结果里。
                    if let item = ClaudeTasks.created(fromResult: obj["toolUseResult"]) {
                        out.append(ev(.todoUpdate, todos: [item]))
                    }
                    return out
                }
                let text = blocks.compactMap { $0["type"] as? String == "text" ? $0["text"] as? String : nil }
                    .joined(separator: "\n")
                return promptEvents(text, hasOtherBlocks: !blocks.isEmpty)
            }
            if let text = content as? String {
                return promptEvents(text, hasOtherBlocks: false)
            }
            return []

        case "assistant":
            guard let message = obj["message"] as? [String: Any] else { return [] }
            if let role = message["role"] as? String, role != "assistant" { return [] }
            if obj["isMeta"] as? Bool == true || obj["isCompactSummary"] as? Bool == true { return [] }
            if let id = obj["uuid"] as? String, id == turn.completedAnswerID { return [] }
            turn.latestTimestamp = ts
            turn.answerID = nil
            if message["model"] as? String == "<synthetic>" {
                // 客户端合成的消息：本轮不会再有真实回答。
                // API 报错带 isApiErrorMessage=true，算失败；“No response requested.”等中断提示不算。
                return [ev(obj["isApiErrorMessage"] as? Bool == true ? .taskFailed : .taskAbort)]
            }
            let stop = message["stop_reason"] as? String
            let blocks = (message["content"] as? [[String: Any]]) ?? []
            let hasTools = blocks.contains { $0["type"] as? String == "tool_use" }
            let responseID = message["id"] as? String
            if responseID == nil || responseID != turn.responseID {
                turn.responseID = responseID
                turn.responseHasTools = false
            }
            turn.responseHasTools = turn.responseHasTools || hasTools
            let hasText = blocks.contains {
                $0["type"] as? String == "text" && !(($0["text"] as? String) ?? "").trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            }
            if stop == "end_turn", hasText, !turn.responseHasTools {
                turn.answerID = obj["uuid"] as? String
                turn.answerTimestamp = ts
                turn.answerEntrypoint = obj["entrypoint"] as? String
            }
            var out: [PetEvent] = []
            for b in blocks {
                switch b["type"] as? String {
                case "tool_use":
                    let name = (b["name"] as? String) ?? ""
                    let input = (b["input"] as? [String: Any]) ?? [:]
                    // The last box of the turn decides; a later plain recap withdraws the question.
                    if name == Self.nextStepTool { turn.handoffQuestion = Self.blockingQuestion(nextStep: input) }
                    let activity: PetState?
                    switch ClaudeToolClassifier.classify(tool: name, input: input) {
                    case .activity(let s): activity = s
                    case .continuePrevious: activity = nil
                    }
                    out.append(ev(.activityStart, id: b["id"] as? String, activity: activity, tool: name,
                                  detail: ClaudeToolClassifier.describe(tool: name, input: input),
                                  question: ClaudeToolClassifier.question(tool: name, input: input)))
                    if let t = ClaudeTasks.events(tool: name, input: input) {
                        out.append(ev(t.kind, todos: t.items))
                    }
                case "thinking", "redacted_thinking":
                    out.append(ev(.thinking))
                case "text":
                    // stop_sequence can be followed immediately by another API
                    // request. Even end_turn still precedes the Stop-hook decision.
                    out.append(ev(.thinking))
                default:
                    break
                }
            }
            return out

        case "system":
            if obj["subtype"] as? String == "api_error" {
                turn.latestTimestamp = ts
                turn.answerID = nil
                return [ev(.thinking)] // The client may retry; this is not its terminal API error.
            }
            let subtype = obj["subtype"] as? String
            guard subtype == "stop_hook_summary" || subtype == "turn_duration",
                  let answer = turn.answerID, obj["parentUuid"] as? String == answer else { return [] }
            if subtype == "turn_duration" {
                guard turn.answerEntrypoint == "cli", obj["entrypoint"] as? String == "cli",
                      let number = obj["durationMs"] as? NSNumber, CFGetTypeID(number) != CFBooleanGetTypeID(),
                      number.doubleValue.isFinite, number.doubleValue >= 0 else { return [] }
            }
            turn.latestTimestamp = ts
            turn.answerID = nil
            let stopped = subtype == "turn_duration" || (obj["preventedContinuation"] as? Bool == false
                && obj["hasOutput"] as? Bool == false
                && (obj["hookErrors"] as? [Any])?.isEmpty == true
                && (obj["hookAdditionalContext"] as? [Any])?.isEmpty == true
                && ((obj["stopReason"] as? String) ?? "").isEmpty)
            let backgroundPending = turn.hookPromptID.flatMap { turn.stops[$0] }.map {
                $0.receivedAt >= turn.answerTimestamp && $0.hasPendingWork
            } ?? false
            guard stopped, !backgroundPending, !turn.pending else { return [ev(.thinking)] }
            turn.completedAnswerID = answer
            return Self.ended(turn, at: ts, session: session)

        case "api-request":
            // Only the observed desktop main-loop request shape is recognized;
            // title generation or other helper queries must not revive a task.
            guard obj["querySource"] as? String == "sdk" else { return [] }
            turn.latestTimestamp = ts
            turn.answerID = nil
            return [ev(.thinking)]

        default:
            return []
        }
    }

    private func userText(_ text: String, hasOtherBlocks: Bool) -> PetEvent.Kind? {
        let t = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if t.hasPrefix("[Request interrupted by user") { return .taskAbort }
        // 本地命令（/clear、/model 等）的回显不会触发模型回答。
        if t.hasPrefix("<local-command-") || t.hasPrefix("<command-name>") || t.hasPrefix("<command-message>") {
            return nil
        }
        if t.isEmpty && !hasOtherBlocks { return nil }
        return .taskStart
    }

    /// 请求的第一行（跳过标签行、合并空白），没有会话标题时当作“大任务”。
    static func promptLine(_ text: String) -> String? {
        for raw in text.split(whereSeparator: \.isNewline) {
            let line = raw.split(whereSeparator: \.isWhitespace).joined(separator: " ")
            if line.isEmpty || line.hasPrefix("<") { continue }
            return String(line.prefix(80))
        }
        return nil
    }

    /// 工具结果是否算失败：is_error 为真，且不是用户拒绝授权或中断（这两种不让她沮丧）。
    static func isFailure(_ result: [String: Any]) -> Bool {
        guard result["is_error"] as? Bool == true else { return false }
        let text: String
        if let s = result["content"] as? String {
            text = s
        } else if let parts = result["content"] as? [[String: Any]] {
            text = parts.compactMap { $0["text"] as? String }.joined(separator: "\n")
        } else {
            text = ""
        }
        return !(text.contains("doesn't want to proceed") || text.hasPrefix("[Request interrupted"))
    }
}

/// Claude Code 官方 hooks 的 stdin JSON → 事件。
/// 需要用户自行在 settings.json 中启用 hooks（见 integrations/claude-hooks）。
public struct ClaudeHookParser: Sendable {
    public static let source = "claude-hook"

    public init() {}

    /// receivedAt：播放器收到这条记录的时间（hook 输入本身不带时间戳）。
    public func events(from obj: [String: Any], receivedAt: Double) -> [PetEvent] {
        guard let name = obj["hook_event_name"] as? String,
              let session = obj["session_id"] as? String else { return [] }
        if obj["agent_id"] != nil || obj["isSidechain"] as? Bool == true { return [] }
        let ts = (obj["yukio_ts_ms"] as? Double) ?? receivedAt
        func ev(_ kind: PetEvent.Kind, id: String? = nil, activity: PetState? = nil, tool: String? = nil,
                detail: String? = nil, todos: [TodoItem]? = nil, question: PetQuestion? = nil) -> PetEvent {
            PetEvent(ts: ts, source: Self.source, session: session, kind: kind, eventID: id, activity: activity,
                     tool: tool, detail: detail, todos: todos, question: question)
        }
        switch name {
        case "UserPromptSubmit":
            return [ev(.taskStart, detail: (obj["prompt"] as? String).flatMap(ClaudeTranscriptParser.promptLine))]
        case "PreToolUse":
            let tool = (obj["tool_name"] as? String) ?? ""
            let input = (obj["tool_input"] as? [String: Any]) ?? [:]
            let activity: PetState?
            switch ClaudeToolClassifier.classify(tool: tool, input: input) {
            case .activity(let s): activity = s
            case .continuePrevious: activity = nil
            }
            var out = [ev(.activityStart, id: obj["tool_use_id"] as? String, activity: activity, tool: tool,
                          detail: ClaudeToolClassifier.describe(tool: tool, input: input),
                          question: ClaudeToolClassifier.question(tool: tool, input: input))]
            if let t = ClaudeTasks.events(tool: tool, input: input) {
                out.append(ev(t.kind, todos: t.items))
            }
            return out
        case "PostToolUse":
            // Claude Code 只在工具成功后触发 PostToolUse，失败时通常不发这条；
            // 工具失败与整轮失败由会话转录的 is_error / API 报错条目补上（两个来源按 tool_use_id 去重）。
            // 万一响应里带了错误信息，这里也认出来。
            var out = [ev(Self.isFailure(obj["tool_response"]) ? .activityFailed : .activityEnd,
                          id: obj["tool_use_id"] as? String, tool: obj["tool_name"] as? String)]
            if let item = ClaudeTasks.created(fromResult: obj["tool_response"]) {
                out.append(ev(.todoUpdate, todos: [item]))
            }
            return out
        case "Stop":
            // This is an attempted stop, before the aggregate hook decision.
            // Completion is confirmed by the matching transcript summary instead.
            return []
        case "PostToolUseFailure":
            return [ev(obj["is_interrupt"] as? Bool == true ? .activityEnd : .activityFailed,
                       id: obj["tool_use_id"] as? String, tool: obj["tool_name"] as? String)]
        case "StopFailure":
            return [ev(.taskFailed)]
        case "SessionEnd":
            return [ev(.taskAbort)]
        default:
            return []
        }
    }

    /// hook 的 tool_response 是否表示失败：带 is_error 或非空 error 字段。
    /// 你拒绝授权、主动中断都不算她的失败。
    static func isFailure(_ response: Any?) -> Bool {
        guard let dict = response as? [String: Any], dict["is_interrupt"] as? Bool != true else { return false }
        let text = (dict["error"] as? String) ?? ""
        guard dict["is_error"] as? Bool == true || !text.isEmpty else { return false }
        return !(text.contains("doesn't want to proceed") || text.hasPrefix("[Request interrupted"))
    }
}

/// Claude Code 任务清单工具 → 任务清单事件。
/// TodoWrite 每次给出完整清单；TaskCreate 的编号在结果里（toolUseResult.task）；TaskUpdate 给出编号与新状态。
enum ClaudeTasks {
    static func events(tool: String, input: [String: Any]) -> (kind: PetEvent.Kind, items: [TodoItem])? {
        switch tool {
        case "TodoWrite":
            guard let todos = input["todos"] as? [[String: Any]] else { return nil }
            let items = todos.enumerated().map { (i, t) in
                TodoItem(id: idString(t["id"]) ?? String(i),
                         subject: (t["content"] as? String) ?? (t["activeForm"] as? String),
                         status: (t["status"] as? String).flatMap(TodoItem.Status.init(rawValue:)) ?? .pending)
            }
            return (.todoList, items)
        case "TaskUpdate":
            guard let id = idString(input["taskId"]) else { return nil }
            let status = (input["status"] as? String).flatMap(TodoItem.Status.init(rawValue:))
            let subject = input["subject"] as? String
            guard status != nil || subject != nil else { return nil }
            return (.todoUpdate, [TodoItem(id: id, subject: subject, status: status)])
        default:
            return nil
        }
    }

    /// TaskCreate 的结果：{"task": {"id": "3", "subject": "…"}}。
    static func created(fromResult result: Any?) -> TodoItem? {
        guard let task = (result as? [String: Any])?["task"] as? [String: Any],
              let id = idString(task["id"]), let subject = task["subject"] as? String else { return nil }
        return TodoItem(id: id, subject: subject)
    }

    static func idString(_ v: Any?) -> String? {
        if let s = v as? String { return s }
        if let n = v as? Int { return String(n) }
        return nil
    }
}

/// 从字节流中切出完整的顶层 JSON 对象。兼容 JSONL（一行一个）与多行 JSON 直接拼接。
public struct JSONObjectStream: Sendable {
    private var buffer = Data()
    private var scanIndex = 0
    private var depth = 0
    private var inString = false
    private var escape = false
    private var objectStart: Int?
    public var maxBufferBytes = 16 * 1024 * 1024

    public init() {}

    public mutating func append(_ data: Data) -> [Data] {
        buffer.append(data)
        var out: [Data] = []
        buffer.withUnsafeBytes { (raw: UnsafeRawBufferPointer) in
            let bytes = raw.bindMemory(to: UInt8.self)
            while scanIndex < bytes.count {
                let b = bytes[scanIndex]
                if objectStart == nil {
                    if b == UInt8(ascii: "{") { objectStart = scanIndex; depth = 1; inString = false; escape = false }
                } else if inString {
                    if escape { escape = false }
                    else if b == UInt8(ascii: "\\") { escape = true }
                    else if b == UInt8(ascii: "\"") { inString = false }
                } else {
                    switch b {
                    case UInt8(ascii: "\""): inString = true
                    case UInt8(ascii: "{"), UInt8(ascii: "["): depth += 1
                    case UInt8(ascii: "}"), UInt8(ascii: "]"):
                        depth -= 1
                        if depth == 0, let start = objectStart {
                            out.append(Data(bytes[start...scanIndex]))
                            objectStart = nil
                        }
                    default: break
                    }
                }
                scanIndex += 1
            }
        }
        // 丢弃已处理部分。
        let keepFrom = objectStart ?? scanIndex
        if keepFrom > 0 {
            buffer.removeSubrange(0..<keepFrom)
            scanIndex -= keepFrom
            if objectStart != nil { objectStart = 0 }
        }
        if buffer.count > maxBufferBytes {
            buffer.removeAll(); scanIndex = 0; objectStart = nil; depth = 0; inString = false
        }
        return out
    }
}
