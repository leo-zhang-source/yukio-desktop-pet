import Foundation

/// UI acknowledgement survives a temporary focus change or hiding the pet.
/// It never asserts that the remote assistant accepted an injected answer.
public struct QuestionPresentationState {
    public struct Key: Hashable {
        public let session: String
        public let callID: String
        public let source: String
        public let generation: String
        public init(_ pending: ActivityRouter.PendingQuestion) {
            session = pending.session
            callID = pending.presentationCallID
            source = pending.source
            generation = pending.generation
        }
    }
    private struct Record {
        var dismissed = false
        var notice: String?
        var draft = ""
        var picked: Set<Int> = []
        var submission: UUID?
        let diagnosticID = UUID().uuidString
    }
    private var records: [Key: Record] = [:]
    private var order: [Key] = []
    public init() {}

    public var hasSubmissions: Bool { records.values.contains { $0.submission != nil } }
    public func isSending(_ key: Key) -> Bool { records[key]?.submission != nil }
    public mutating func beginSubmission(_ key: Key) -> UUID? {
        guard !isSending(key) else { return nil }
        remember(key)
        let token = UUID()
        records[key]?.submission = token
        return token
    }
    /// Only the current attempt may finish; duplicate/late callbacks are ignored.
    @discardableResult public mutating func finishSubmission(_ key: Key, token: UUID) -> Bool {
        guard records[key]?.submission == token else { return false }
        records[key]?.submission = nil
        return true
    }

    public func isDismissed(_ key: Key) -> Bool { records[key]?.dismissed == true }
    public func notice(for key: Key) -> String? { records[key]?.notice }
    public mutating func dismiss(_ key: Key) { remember(key); records[key]?.dismissed = true }
    public mutating func reopen(_ key: Key) { remember(key); records[key]?.dismissed = false }
    public func draft(for key: Key) -> String { records[key]?.draft ?? "" }
    public func picked(for key: Key) -> Set<Int> { records[key]?.picked ?? [] }
    public mutating func saveDraft(_ value: String, picked: Set<Int>, for key: Key) {
        remember(key); records[key]?.draft = value; records[key]?.picked = picked
    }
    public mutating func diagnosticID(for key: Key) -> String {
        remember(key); return records[key]!.diagnosticID
    }
    public mutating func setNotice(_ value: String, for key: Key) { remember(key); records[key]?.notice = value }
    private mutating func remember(_ key: Key) {
        guard records[key] == nil else { return }
        records[key] = Record()
        order.append(key)
        // Never silently discard a user's draft or a running answer to make room.
        if order.count > 512, let index = order.firstIndex(where: {
            guard $0 != key, let record = records[$0] else { return false }
            return record.draft.isEmpty && record.picked.isEmpty && record.submission == nil && record.dismissed
        }) { records.removeValue(forKey: order.remove(at: index)) }
    }
}
