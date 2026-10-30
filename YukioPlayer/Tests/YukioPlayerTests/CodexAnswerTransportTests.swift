import Foundation
import Testing
import YukioCore
@testable import YukioPlayer

/// Adapted from preserved local-chat-cards tests; all traffic uses our own fixture.
@Suite struct CodexAnswerTransportTests {
    @Test(arguments: [false, true])
    func unicodeAnswerReachesOnlyTheExactFixtureQuestion(canonical: Bool) throws {
        let root = URL(fileURLWithPath: "/tmp/yukio-stage2-" + UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let repo = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        let fixture = repo.appendingPathComponent("tests/remediation/fixtures/codex_reply_server.py")
        let server = Process()
        server.executableURL = URL(fileURLWithPath: ProcessInfo.processInfo.environment["YUKIO_TEST_PYTHON"] ?? "/usr/bin/python3")
        server.arguments = [fixture.path, "--root", root.path] + (canonical ? ["--canonical"] : [])
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
        try CodexAnswerClient(socketPath: root.appendingPathComponent("ipc.sock").path)
            .send(session: "fixture-session", callID: "fixture-call", question: question, answer: "中文测试答案\n第二行")
        let exitDeadline = Date().addingTimeInterval(6)
        while server.isRunning, Date() < exitDeadline { Thread.sleep(forTimeInterval: 0.02) }
        try #require(!server.isRunning, "Fixture did not stop after the answer")
        let diagnostic = try String(contentsOf: log, encoding: .utf8)
        #expect(server.terminationStatus == 0, "\(diagnostic)")
        let receipt = try #require(JSONSerialization.jsonObject(with: Data(contentsOf: root.appendingPathComponent("receipt.json"))) as? [String: Any])
        #expect(receipt["accepted"] as? Bool == true)
        #expect(receipt["answer"] as? String == "中文测试答案\n第二行")
        #expect(receipt["session"] as? String == "fixture-session")
        #expect(receipt["call"] as? String == "fixture-call")
        #expect((receipt["methods"] as? [String])?.contains("thread-follower-steer-turn") == true)
    }
}
