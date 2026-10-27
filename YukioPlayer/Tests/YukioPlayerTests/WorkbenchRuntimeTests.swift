import Foundation
import Testing
@testable import YukioPlayer

@Suite @MainActor struct WorkbenchRuntimeTests {
    private func fixture(_ script: String) throws -> URL {
        let resources = FileManager.default.temporaryDirectory.appendingPathComponent("yukio-runtime-test-\(UUID())")
        let executable = resources.appendingPathComponent("activity-workbench/runtime/YukioRuntime/YukioRuntime")
        try FileManager.default.createDirectory(at: executable.deletingLastPathComponent(), withIntermediateDirectories: true)
        try ("#!/bin/sh\n" + script + "\n").write(to: executable, atomically: true, encoding: .utf8)
        try FileManager.default.setAttributes([.posixPermissions: 0o700], ofItemAtPath: executable.path)
        return resources
    }

    private func start(_ runtime: WorkbenchRuntime) async -> Result<URL, Error> {
        await withCheckedContinuation { continuation in runtime.start { continuation.resume(returning: $0) } }
    }

    @Test func protocolAcceptsOnlyExplicitLoopbackReadiness() {
        #expect(WorkbenchRuntime.readinessURL("YUKIO_WORKBENCH_READY {\"url\":\"http://127.0.0.1:52123/\"}")?.port == 52123)
        for url in ["https://127.0.0.1:8767/", "http://localhost:8767/", "http://example.com:8767/", "http://user@127.0.0.1:8767/", "http://127.0.0.1:0/", "http://127.0.0.1:8767/path", "http://127.0.0.1:8767/?secret=value"] {
            #expect(WorkbenchRuntime.readinessURL("YUKIO_WORKBENCH_READY {\"url\":\"\(url)\"}") == nil)
        }
        #expect(WorkbenchRuntime.readinessURL("Failed to connect to http://127.0.0.1:8767/") == nil)
        #expect(WorkbenchRuntime.startupFailure("YUKIO_WORKBENCH_ERROR {\"code\":\"private arbitrary text\"}") == nil)
    }

    @Test func splitReadinessOutputReturnsTheSelectedPort() async throws {
        let root = try fixture("printf 'YUKIO_WORKBENCH_READY '; /bin/sleep 0.03; printf '{\"url\":\"http://127.0.0.1:52123/\"}\\n'; exec /bin/sleep 3")
        let runtime = WorkbenchRuntime(resources: root)
        defer { runtime.stop(); try? FileManager.default.removeItem(at: root) }
        #expect(try await start(runtime).get().port == 52123)
    }

    @Test func immediateReuseExitStillDeliversReadinessExactlyOnce() async throws {
        let root = try fixture("printf 'YUKIO_WORKBENCH_READY {\"url\":\"http://127.0.0.1:52124/\"}\\n'")
        defer { try? FileManager.default.removeItem(at: root) }
        for _ in 0..<5 {
            let runtime = WorkbenchRuntime(resources: root)
            #expect(try await start(runtime).get().port == 52124)
            runtime.stop()
        }
    }

    @Test func startupFailureIsReportedAndRetryCanRecover() async throws {
        let root = try fixture("printf 'YUKIO_WORKBENCH_ERROR {\"code\":\"invalid_configuration\"}\\n' >&2; exit 1")
        let runtime = WorkbenchRuntime(resources: root)
        defer { runtime.stop(); try? FileManager.default.removeItem(at: root) }
        let failed = await start(runtime)
        guard case .failure(let error) = failed else { Issue.record("Expected startup failure"); return }
        #expect((error as? WorkbenchRuntime.Failure)?.code == "invalid_configuration")
        runtime.stop()
        let path = root.appendingPathComponent("activity-workbench/runtime/YukioRuntime/YukioRuntime")
        try "#!/bin/sh\nprintf 'YUKIO_WORKBENCH_READY {\"url\":\"http://127.0.0.1:52125/\"}\\n'\n".write(to: path, atomically: false, encoding: .utf8)
        #expect(try await start(runtime).get().port == 52125)
    }

    @Test func silentStartupTimesOutInsteadOfHangingReconnect() async throws {
        let root = try fixture("exec /bin/sleep 5")
        let runtime = WorkbenchRuntime(resources: root, startupTimeout: 0.2)
        defer { runtime.stop(); try? FileManager.default.removeItem(at: root) }
        guard case .failure(let error) = await start(runtime) else { Issue.record("Expected timeout"); return }
        #expect((error as? WorkbenchRuntime.Failure)?.code == "startup_timeout")
    }

    @Test func failedRuntimeOutputCannotBeMistakenForAReadyURL() async throws {
        let root = try fixture("printf 'Failed to connect to http://127.0.0.1:8767/\\n'; exit 7")
        let runtime = WorkbenchRuntime(resources: root)
        defer { runtime.stop(); try? FileManager.default.removeItem(at: root) }
        guard case .failure(let error) = await start(runtime) else { Issue.record("Expected exit failure"); return }
        #expect((error as? WorkbenchRuntime.Failure)?.code == "runtime_exit_7")
    }
}
