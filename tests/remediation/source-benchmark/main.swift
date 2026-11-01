import Foundation

let root = URL(fileURLWithPath: CommandLine.arguments[1])
let mode = CommandLine.arguments[2]
let fm = FileManager.default
try fm.createDirectory(at: root, withIntermediateDirectories: true)
let codexRoot = root.appendingPathComponent("codex/sessions")
let claudeRoot = root.appendingPathComponent("claude/projects")
let codex = CodexSessionsSource(sessionsDir: codexRoot)
let claude = ClaudeTranscriptSource(projectsDir: claudeRoot)
let stamp = ISO8601DateFormatter().string(from: Date())
var files: [(URL, String, Bool)] = []
for (source, folder) in [("codex", codexRoot), ("claude", claudeRoot.appendingPathComponent("test"))] {
    try fm.createDirectory(at: folder, withIntermediateDirectories: true)
    for i in 0..<2 {
        let id = source + "-" + String(i)
        let file = folder.appendingPathComponent(id + ".jsonl")
        let row: [String: Any] = source == "codex"
            ? ["type":"session_meta", "payload":["id":id]]
            : ["type":"user", "sessionId":id, "timestamp":stamp, "message":["role":"user", "content":"Synthetic performance fixture"]]
        var data = try JSONSerialization.data(withJSONObject: row); data.append(10)
        try data.write(to:file)
        files.append((file,id,source == "codex"))
    }
}
let epoch = Date().timeIntervalSince1970 * 1000
_ = claude.poll(now: epoch); _ = codex.poll(now: epoch)
var measurements: [[String: Any]] = []
var totalEvents = 0
var observed: [String: [String]] = [:]
let perFile = mode == "idle" ? 0 : mode == "normal" ? 10 : 1000
for cycle in 0..<6 {
    if cycle < (mode == "burst" ? 1 : 6) {
        for (file,id,isCodex) in files {
            var data = Data()
            for index in 0..<perFile {
                let call = "\(id)-\(cycle)-\(index)"
                let row: [String: Any] = isCodex
                    ? ["timestamp":stamp,"type":"response_item","payload":["type":"function_call","call_id":call,"name":"exec_command","arguments":"{\"cmd\":\"pwd\"}"]]
                    : ["type":"assistant","sessionId":id,"timestamp":stamp,"message":["stop_reason":"tool_use","content":[["type":"tool_use","id":call,"name":"Bash","input":["command":"pwd"]]]]]
                data.append(try JSONSerialization.data(withJSONObject:row)); data.append(10)
            }
            let h = try FileHandle(forWritingTo:file); try h.seekToEnd(); try h.write(contentsOf:data); try h.close()
        }
    }
    let start = ProcessInfo.processInfo.systemUptime
    let claudeEvents = claude.poll(now: epoch + Double(cycle+1) * 300)
    let middle = ProcessInfo.processInfo.systemUptime
    let codexEvents = codex.poll(now: epoch + Double(cycle+1) * 300)
    let end = ProcessInfo.processInfo.systemUptime
    totalEvents += claudeEvents.count + codexEvents.count
    for event in claudeEvents + codexEvents {
        if let id = event.eventID { observed[event.source + ":" + event.session, default: []].append(id) }
    }
    measurements.append(["claude_ms":(middle-start)*1000,"codex_ms":(end-middle)*1000,"total_ms":(end-start)*1000,"events":claudeEvents.count+codexEvents.count])
}
let sizes = try files.map { try $0.0.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? 0 }
let expectedTotal = perFile * 4 * (mode == "burst" ? 1 : 6)
var ordered = totalEvents == expectedTotal
for (_, id, isCodex) in files {
    let source = isCodex ? CodexRolloutParser.source : ClaudeTranscriptParser.source
    let expected = (0..<(mode == "burst" ? 1 : 6)).flatMap { cycle in (0..<perFile).map { "\(id)-\(cycle)-\($0)" } }
    ordered = ordered && (observed[source + ":" + id] ?? []) == expected
}
let result: [String:Any] = ["mode":mode,"source_chats":4,"per_file_append":perFile,"fixture_bytes":sizes.reduce(0,+),"main_thread":Thread.isMainThread,"events":totalEvents,"identity_and_order_passed":ordered,"polls":measurements]
print(String(data:try JSONSerialization.data(withJSONObject:result,options:[.sortedKeys]),encoding:.utf8)!)
if !ordered { exit(1) }
