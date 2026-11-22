import Foundation
#if canImport(Darwin)
import Darwin
#endif

/// Optional, read-only Claude process registry. This is a versioned internal
/// client format, not a completion signal. Never read peer credentials or sockets.
public final class ClaudeRuntimeIndex {
    struct Entry: Equatable {
        let pid: Int32
        let session: String
        let status: String
        let updatedAt: Double
        let processStart: String
    }
    let root: URL
    let matchesProcess: (Int32, String) -> Bool
    private var known: [String: Entry] = [:]
    private(set) var exited: Set<String> = []

    public convenience init(root: URL) {
        self.init(root: root, matchesProcess: Self.matchesProcess)
    }
    init(root: URL, matchesProcess: @escaping (Int32, String) -> Bool) {
        self.root = root; self.matchesProcess = matchesProcess
    }
    static func matchesProcess(_ pid: Int32, _ start: String) -> Bool {
        #if canImport(Darwin)
        var info = proc_bsdinfo()
        guard proc_pidinfo(pid, PROC_PIDTBSDINFO, 0, &info, Int32(MemoryLayout.size(ofValue: info))) == MemoryLayout.size(ofValue: info),
              info.pbi_uid == getuid() else { return false }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "EEE MMM d HH:mm:ss yyyy"
        guard let date = formatter.date(from: start) else { return false }
        return abs(date.timeIntervalSince1970 - Double(info.pbi_start_tvsec)) < 1
        #else
        return false
        #endif
    }
    func snapshot(now: Double) -> [String: Entry] {
        let fm = FileManager.default
        var result: [String: Entry] = [:], conflicts: Set<String> = []
        let paths = (try? fm.contentsOfDirectory(at: root, includingPropertiesForKeys: [.isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey])) ?? []
        for path in paths.prefix(1024) {
            guard path.pathExtension == "json", let pid = Int32(path.deletingPathExtension().lastPathComponent), pid > 0,
                  let info = try? path.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey]),
                  info.isRegularFile == true, info.isSymbolicLink != true, (info.fileSize ?? Int.max) <= 16 << 10,
                  let handle = try? FileHandle(forReadingFrom: path) else { continue }
            let data = try? handle.read(upToCount: (16 << 10) + 1); try? handle.close()
            guard let data, data.count <= 16 << 10,
                  let row = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
                  row["pid"] as? Int32 == pid, row["pidDomain"] as? String == "darwin",
                  let session = row["sessionId"] as? String, UUID(uuidString: session) != nil,
                  let state = row["status"] as? String, ["busy", "waiting", "idle"].contains(state),
                  let start = row["procStart"] as? String, start.count <= 64,
                  let at = row["updatedAt"] as? Double, at.isFinite, at >= 0, at <= now + 1000,
                  matchesProcess(pid, start) else { continue }
            if result[session] != nil { conflicts.insert(session) }
            result[session] = Entry(pid: pid, session: session, status: state == "busy" ? "working" : state, updatedAt: at, processStart: start)
        }
        for session in conflicts { result.removeValue(forKey: session) }
        // A missing / partially written registry alone is not proof of exit.
        exited = Set(known.compactMap { session, entry in
            result[session] == nil && !matchesProcess(entry.pid, entry.processStart) ? session : nil
        })
        // Retain unseen identities to detect exit, but don't replay stale status.
        for session in exited.union(conflicts) { known.removeValue(forKey: session) }
        for (session, entry) in result { known[session] = entry }
        return result
    }
}
