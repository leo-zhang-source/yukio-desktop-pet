import Foundation

/// UI acknowledgement survives a temporary focus change or hiding the pet.
/// It never asserts that the remote assistant accepted an injected answer.
public struct QuestionPresentationState {
    public struct Key: Hashable {
        public let session: String
        public let callID: String
        public init(_ pending: ActivityRouter.PendingQuestion) {
            session = pending.session
            callID = pending.callID
        }
    }
    private struct Record {
        var dismissed = false
        var notice: String?
        var draft = ""
        var picked: Set<Int> = []
        let diagnosticID = UUID().uuidString
    }
    private var records: [Key: Record] = [:]
    private var order: [Key] = []
    public init() {}

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
        if order.count > 512 { records.removeValue(forKey: order.removeFirst()) }
    }
}
