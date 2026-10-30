import AppKit
import Darwin
import Foundation
import Testing
@testable import YukioPlayer

@Suite @MainActor struct WorkbenchRuntimeTests {
    @Test func readinessRequiresTheProtocolAndAnExactLoopbackOrigin() {
        #expect(WorkbenchRuntime.readinessURL("YUKIO_WORKBENCH_READY {\"url\":\"http://127.0.0.1:41235/\"}")?.port == 41235)
        for line in ["log http://127.0.0.1:8767/", "YUKIO_WORKBENCH_READY not-json",
                     "prefix YUKIO_WORKBENCH_READY {\"url\":\"http://127.0.0.1:41235/\"}"] {
            #expect(WorkbenchRuntime.readinessURL(line) == nil)
        }
        for address in ["http://evil.invalid:8767/", "file:///tmp/test", "http://user@127.0.0.1:8767/",
                        "http://127.0.0.1:0/", "http://127.0.0.1:8767/?token=private", "http://127.0.0.1:8767/other"] {
            #expect(WorkbenchRuntime.readinessURL("YUKIO_WORKBENCH_READY {\"url\":\"\(address)\"}") == nil)
        }
        #expect(WorkbenchRuntime.startupFailure("YUKIO_WORKBENCH_ERROR {\"code\":\"port_in_use\"}")?.code == "port_in_use")
        #expect(WorkbenchRuntime.startupFailure("YUKIO_WORKBENCH_ERROR {\"code\":\"/private/path\"}") == nil)
    }

    @Test func reconnectionKeepsSelectionAtTheNewOriginOnly() {
        let new = URL(string: "http://127.0.0.1:41235/")!
        let restored = WorkbenchPanelController.restoreSelection(URL(string: "http://127.0.0.1:8767/history?client=codex&key=fixture"), at: new)
        #expect(restored.port == 41235 && restored.path == "/history")
        #expect(restored.query == "client=codex&key=fixture")
        #expect(WorkbenchPanelController.restoreSelection(URL(string: "https://other.invalid/private"), at: new) == new)
        #expect(!WorkbenchPanelController.isLocal(URL(string: "http://127.0.0.1:8767/")!, port: 41235))
    }

    private func fixture(_ body: String) throws -> URL {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent("workbench-runtime-\(UUID())")
        let executable = root.appendingPathComponent("activity-workbench/runtime/YukioRuntime/YukioRuntime")
        try FileManager.default.createDirectory(at: executable.deletingLastPathComponent(), withIntermediateDirectories: true)
        try Data(("#!/bin/sh\nprintf '%s' \"$$\" > \"$(dirname \"$0\")/test-owner.pid\"\n" + body + "\n").utf8).write(to: executable)
        try FileManager.default.setAttributes([.posixPermissions: 0o700], ofItemAtPath: executable.path)
        return root
    }
    private func start(_ runtime: WorkbenchRuntime) async -> Result<URL, Error> {
        await withCheckedContinuation { continuation in runtime.start { continuation.resume(returning: $0) } }
    }

    @Test func ordinaryURLLogDoesNotBypassStartupTimeout() async throws {
        let root = try fixture("printf 'log http://127.0.0.1:8767/\\n'\nexec /bin/cat >/dev/null")
        let runtime = WorkbenchRuntime(resources: root, startupTimeout: 0.3)
        defer { runtime.stop(); try? FileManager.default.removeItem(at: root) }
        let began = Date()
        let result = await start(runtime)
        guard case .failure(let error) = result else { Issue.record("A log URL was accepted as readiness"); return }
        #expect((error as? WorkbenchRuntime.Failure)?.code == "startup_timeout")
        #expect(Date().timeIntervalSince(began) < 3)
    }

    @Test func startupFailuresRemainSpecificAndPrivate() async throws {
        let root = try fixture("printf 'YUKIO_WORKBENCH_ERROR {\"code\":\"invalid_configuration\"}\\n'\nexit 7")
        let runtime = WorkbenchRuntime(resources: root, startupTimeout: 2)
        defer { runtime.stop(); try? FileManager.default.removeItem(at: root) }
        guard case .failure(let error) = await start(runtime) else { Issue.record("Expected startup failure"); return }
        #expect((error as? WorkbenchRuntime.Failure)?.code == "invalid_configuration")
        let panel = WorkbenchPanelController(runtime: runtime)
        defer { panel.shutdown(); panel.close() }
        panel.showConnectionFailure("Test failure", code: "invalid_configuration")
        #expect(panel.diagnosticText.contains("code=invalid_configuration"))
        #expect(!panel.diagnosticText.contains(root.path))
        panel.showSettings()
        #expect(panel.showingSettings)
    }

    @Test func stopAndRetryTenTimesReleaseOnlyTheOwnedProcess() async throws {
        let root = try fixture("printf 'YUKIO_WORKBENCH_READY {\"url\":\"http://127.0.0.1:41235/\"}\\n'\nexec /bin/cat >/dev/null")
        defer { try? FileManager.default.removeItem(at: root) }
        let runtime = WorkbenchRuntime(resources: root, startupTimeout: 2)
        defer { runtime.stop() }
        for _ in 0..<10 {
            #expect(try await start(runtime).get().port == 41235)
            let pidText = try String(contentsOf: root.appendingPathComponent("activity-workbench/runtime/YukioRuntime/test-owner.pid"), encoding: .utf8)
            let pid = try #require(Int32(pidText))
            #expect(kill(pid, 0) == 0)
            runtime.stop()
            let deadline = Date().addingTimeInterval(3)
            while kill(pid, 0) == 0 && Date() < deadline { try await Task.sleep(nanoseconds: 20_000_000) }
            #expect(kill(pid, 0) == -1 && errno == ESRCH)
        }
    }
}
