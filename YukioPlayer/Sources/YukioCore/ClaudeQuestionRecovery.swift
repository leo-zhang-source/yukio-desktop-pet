import Foundation

/// Restores questions from an old local transcript without replaying old work.
/// No question is inferred from prose, a truncated turn, or a partial result.
enum ClaudeQuestionRecovery {
    static func events(objects: [Data], session: String) -> [PetEvent] {
        let parser = ClaudeTranscriptParser()
        var start: PetEvent?
        var title: PetEvent?
        var questions: [PetEvent] = []
        var ended: Set<String> = []
        var ambiguous = false
        for data in objects {
            guard let row = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { return [] }
            // Metadata may lack a session, but another session's records cannot
            // establish a boundary or receipt for this file.
            if let id = row["sessionId"] as? String, id != session { return [] }
            if row["isSidechain"] as? Bool == true { continue }
            let message = row["message"] as? [String: Any]
            let blocks = message?["content"] as? [[String: Any]] ?? []
            if blocks.contains(where: { $0["type"] as? String == "tool_result" && ($0["tool_use_id"] as? String)?.isEmpty != false }) {
                ambiguous = true
            }
            for event in parser.events(from: row) {
                guard event.session == session else { return [] }
                switch event.kind {
                case .sessionTitle: title = event
                case .taskStart:
                    start = event; questions = []; ended = []; ambiguous = false
                case .taskEnd, .turnEnd, .taskAbort, .taskFailed, .sourceLost:
                    start = nil; questions = []; ended = []; ambiguous = false
                case .activityStart where event.activity == .question_for_user:
                    guard let start, event.ts >= start.ts,
                          let id = event.eventID, !id.isEmpty, event.question != nil else { continue }
                    if ended.contains(id) { ambiguous = true; continue }
                    if let existing = questions.first(where: { $0.eventID == id }) {
                        if existing != event { ambiguous = true }
                    } else { questions.append(event) }
                case .activityEnd, .activityFailed:
                    guard let id = event.eventID, !id.isEmpty else { ambiguous = true; continue }
                    if let question = questions.first(where: { $0.eventID == id }), event.ts < question.ts {
                        ambiguous = true
                    }
                    questions.removeAll { $0.eventID == id }
                    ended.insert(id)
                default: break
                }
            }
        }
        guard let start, !questions.isEmpty, !ambiguous else { return [] }
        return (title.map { [$0] } ?? []) + [start] + questions
    }
}
