import Foundation
import Testing
import YukioCore
@testable import YukioPlayer

/// Adapted from preserved local-chat-cards tests; all traffic uses our own fixture.
@Suite struct CodexAnswerTransportTests {
    @Test(arguments: [0, 1, 2, 3, 4, 5, 6])
    func unicodeAnswerReachesOnlyTheExactFixtureQuestion(scenario: Int) throws {
        let canonical = scenario > 0, completed = scenario == 2, index = scenario == 2 ? 1 : 0
        let root = URL(fileURLWithPath: "/tmp/yukio-stage2-" + UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let repo = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        let fixture = repo.appendingPathComponent("tests/remediation/fixtures/codex_reply_server.py")
        let server = Process()
        server.executableURL = URL(fileURLWithPath: ProcessInfo.processInfo.environment["YUKIO_TEST_PYTHON"] ?? "/usr/bin/python3")
        server.arguments = [fixture.path, "--root", root.path] + (canonical ? ["--canonical"] : []) + (completed ? ["--completed", "--index", "1"] : [])
        if [3, 4].contains(scenario) { server.arguments! += ["--patch-first"] }
        if [4, 6].contains(scenario) { server.arguments! += ["--answered"] }
        if scenario >= 5 { server.arguments! += ["--tail-complete"] }
        let log = root.appendingPathComponent("server.log")
        FileManager.default.createFile(atPath: log.path, contents: nil)
        let handle = try FileHandle(forWritingTo: log)
        defer { try? handle.close() }
        server.standardOutput = handle; server.standardError = handle
        try server.run()
        defer { if server.isRunning { server.terminate(); server.waitUntilExit() } }
        let ready = root.appendingPathComponent("ready").path
        let deadline = Date().addingTimeInterval(5)
        while !FileManager.default.fileExists(atPath: ready), server.isRunning, Date() < deadline {
            Thread.sleep(forTimeInterval: 0.02)
        }
        try #require(FileManager.default.fileExists(atPath: ready), "Fixture did not become ready")
        let question = PetQuestion(text: "人工协议测试：请选择", options: [.init(label: "A"), .init(label: "B")])
        let client = CodexAnswerClient(socketPath: root.appendingPathComponent("ipc.sock").path)
        if [4, 6].contains(scenario) {
            #expect(throws: CodexAnswerClient.Failure.expired) {
                try client.send(session: "fixture-session", callID: "fixture-call", question: question, answer: "中文测试答案\n第二行", questionIndex: index)
            }
        } else {
            try client.send(session: "fixture-session", callID: "fixture-call", question: question, answer: "中文测试答案\n第二行", questionIndex: index)
        }
        let exitDeadline = Date().addingTimeInterval(6)
        while server.isRunning, Date() < exitDeadline { Thread.sleep(forTimeInterval: 0.02) }
        try #require(!server.isRunning, "Fixture did not stop after the answer")
        let diagnostic = try String(contentsOf: log, encoding: .utf8)
        #expect(server.terminationStatus == 0, "\(diagnostic)")
        if [4, 6].contains(scenario) {
            #expect(!FileManager.default.fileExists(atPath: root.appendingPathComponent("receipt.json").path))
            return
        }
        let receipt = try #require(JSONSerialization.jsonObject(with: Data(contentsOf: root.appendingPathComponent("receipt.json"))) as? [String: Any])
        #expect(receipt["accepted"] as? Bool == true)
        #expect(receipt["answer"] as? String == "中文测试答案\n第二行")
        #expect(receipt["session"] as? String == "fixture-session")
        #expect(receipt["call"] as? String == "fixture-call")
        #expect((receipt["methods"] as? [String])?.contains(completed ? "thread-follower-start-turn" : "thread-follower-steer-turn") == true)
    }
}
