import Foundation
import Testing
import YukioCore
@testable import YukioPlayer

@Suite struct CodexAnswerTransportTests {
    @Test(arguments: [false, true])
    func realSocketRoundTripStaysInsideFixture(canonical: Bool) throws {
        // Short AF_UNIX path; every test owns its server, receipt and socket.
        let root = URL(fileURLWithPath: "/tmp/yukio-wire-" + UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let fixture = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
            .deletingLastPathComponent().appendingPathComponent("Fixtures/codex-answer-server.py")
        var script = try String(contentsOf: fixture)
        script = script.replacingOccurrences(of: "root = pathlib.Path(tempfile.mkdtemp(prefix='yukio-codex-fixture-'))",
                                             with: "root = pathlib.Path('\(root.path)')")
        for name in ["card", "click", "server-receipt"] {
            script = script.replacingOccurrences(of: "/tmp/yukio-codex-fixture-\(name).json",
                                                 with: root.appendingPathComponent(name + ".json").path)
        }
        let server = Process(), ready = Pipe(), errors = Pipe()
        server.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        server.arguments = ["-c", script] + (canonical ? ["--canonical"] : [])
        server.standardOutput = ready; server.standardError = errors
        try server.run()
        defer { if server.isRunning { server.terminate(); server.waitUntilExit() } }
        #expect(ready.fileHandleForReading.readData(ofLength: 6) == Data("READY\n".utf8))
        let question = PetQuestion(text: "Codex 协议回传实测：点击测试答案",
                                  options: [.init(label: "YUKIO_CODEX_OK"), .init(label: "YUKIO_CODEX_CANCEL")])
        try CodexAnswerClient(socketPath: root.appendingPathComponent("ipc.sock").path)
            .send(session: "fixture-session", callID: "fixture-call", question: question, answer: "YUKIO_CODEX_OK")
        server.waitUntilExit()
        #expect(server.terminationStatus == 0, "\(String(decoding: errors.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self))")
        let receipt = try #require(JSONSerialization.jsonObject(with: Data(contentsOf: root.appendingPathComponent("server-receipt.json"))) as? [String: Any])
        #expect(receipt["accepted"] as? Bool == true)
        #expect(receipt["answer"] as? String == "YUKIO_CODEX_OK")
        #expect(receipt["navigationMessages"] as? Int == 0)
    }
}
