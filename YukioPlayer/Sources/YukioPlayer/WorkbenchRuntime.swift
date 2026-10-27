import Foundation

/// Each App-owned runtime reserves a loopback port with the OS. It never borrows
/// a service that could belong to another App or a previous attempt shutting down.
final class WorkbenchRuntime: WorkbenchStarting {
    enum Failure: Error {
        case missing, unavailable, timedOut
        case startup(String), launch(Int), exited(Int32)

        var code: String {
            switch self {
            case .missing: return "runtime_missing"
            case .unavailable: return "runtime_unavailable"
            case .timedOut: return "startup_timeout"
            case .startup(let code): return code
            case .launch(let code): return "launch_\(code)"
            case .exited(let status): return "runtime_exit_\(status)"
            }
        }
        func message(english: Bool) -> String {
            switch code {
            case "runtime_missing": return english ? "The workbench component is missing. Install the complete Yukio app again." : "工作台组件缺失，请重新安装完整的 Yukio App。"
            case "invalid_configuration": return english ? "The saved model configuration could not be read. Copy the diagnostics for support." : "保存的模型配置无法读取，请复制诊断信息交给开发者检查。"
            case "data_unavailable": return english ? "The workbench could not open its local data folder. Copy the diagnostics for support." : "工作台无法打开本机记录目录，请复制诊断信息交给开发者检查。"
            case "port_in_use": return english ? "The local connection is occupied. Try Reconnect." : "本机连接地址被占用，请点“重新连接”。"
            case "startup_timeout": return english ? "The workbench took too long to start. Try Reconnect." : "工作台启动超时，请点“重新连接”。"
            default: return english ? "The workbench could not start. Copy the diagnostics for support, or try Reconnect." : "工作台启动失败，请复制诊断信息交给开发者，或点“重新连接”。"
            }
        }
    }
    private var process: Process?
    private var output: Pipe?
    private var timeout: DispatchWorkItem?
    private var readyURL: URL?
    private var generation = UUID()
    private var callbacks: [(Result<URL, Error>) -> Void] = []
    private let resources: URL?
    private let startupTimeout: TimeInterval
    private let launchArguments: [String]
    init(resources: URL? = Bundle.main.resourceURL, startupTimeout: TimeInterval = 15,
         launchArguments: [String] = ["--collect", "--no-browser", "--port", "0"]) {
        self.resources = resources; self.startupTimeout = startupTimeout; self.launchArguments = launchArguments
    }

    static func readinessURL(_ line: String) -> URL? {
        let prefix = "YUKIO_WORKBENCH_READY "
        guard line.hasPrefix(prefix),
              let value = try? JSONSerialization.jsonObject(with: Data(line.dropFirst(prefix.count).utf8)) as? [String: String],
              let address = value["url"], let url = URL(string: address),
              url.scheme == "http", url.host == "127.0.0.1", let port = url.port, (1...65535).contains(port),
              url.user == nil, url.password == nil, url.query == nil, url.fragment == nil, url.path == "/" else { return nil }
        return url
    }

    static func startupFailure(_ line: String) -> Failure? {
        let prefix = "YUKIO_WORKBENCH_ERROR "
        guard line.hasPrefix(prefix),
              let value = try? JSONSerialization.jsonObject(with: Data(line.dropFirst(prefix.count).utf8)) as? [String: String],
              let code = value["code"],
              ["invalid_configuration", "data_unavailable", "port_in_use", "runtime_unavailable"].contains(code) else { return nil }
        return .startup(code)
    }

    func start(_ completion: @escaping (Result<URL, Error>) -> Void) {
        if let readyURL, process?.isRunning == true { completion(.success(readyURL)); return }
        if process?.isRunning == true { callbacks.append(completion); return }
        guard let resources else { completion(.failure(Failure.missing)); return }
        let executable = resources.appendingPathComponent("activity-workbench/runtime/YukioRuntime/YukioRuntime")
        guard FileManager.default.isExecutableFile(atPath: executable.path) else {
            completion(.failure(Failure.missing)); return
        }
        callbacks = [completion]
        let finish: (Result<URL, Error>) -> Void = { [weak self] result in
            guard let self else { return }
            self.timeout?.cancel(); self.timeout = nil
            let waiting = self.callbacks; self.callbacks.removeAll()
            waiting.forEach { $0(result) }
        }
        let token = UUID(); generation = token
        let worker = Process(), pipe = Pipe()
        worker.executableURL = executable
        worker.arguments = launchArguments
        worker.standardOutput = pipe; worker.standardError = pipe
        var pending = "", delivered = false, startupFailure: Failure?
        let accept: (String) -> Void = { [weak self] text in
            guard let self, self.generation == token else { return }
            pending = String((pending + text).suffix(8192))
            while let end = pending.firstIndex(of: "\n") {
                let line = String(pending[..<end]); pending.removeSubrange(...end)
                if let failure = Self.startupFailure(line) { startupFailure = failure }
                if !delivered, let url = Self.readinessURL(line) {
                    delivered = true; self.readyURL = url; finish(.success(url))
                }
            }
        }
        pipe.fileHandleForReading.readabilityHandler = { handle in
            let bytes = handle.availableData
            if bytes.isEmpty {
                handle.readabilityHandler = nil
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) { [weak self] in
                    guard let self, self.generation == token, !delivered else { return }
                    delivered = true
                    finish(.failure(startupFailure ?? (worker.isRunning ? Failure.unavailable : .exited(worker.terminationStatus))))
                }
                return
            }
            let text = String(decoding: bytes, as: UTF8.self)
            DispatchQueue.main.async { accept(text) }
        }
        worker.terminationHandler = { [weak self] _ in
            DispatchQueue.main.async {
                guard let self, self.generation == token else { return }
                // When every recorder was already running the launcher exits cleanly.
                // The pipe's EOF handler reports failures after all readiness output
                // has been consumed, even when a reused launcher exits immediately.
                self.readyURL = nil
            }
        }
        let deadline = DispatchWorkItem { [weak self, weak worker] in
            guard let self, self.generation == token, !delivered else { return }
            delivered = true
            if let worker, worker.isRunning { worker.terminate() }
            finish(.failure(Failure.timedOut))
        }
        timeout = deadline
        DispatchQueue.main.asyncAfter(deadline: .now() + startupTimeout, execute: deadline)
        do { try worker.run(); process = worker; output = pipe }
        catch {
            delivered = true; pipe.fileHandleForReading.readabilityHandler = nil
            finish(.failure(Failure.launch((error as NSError).code)))
        }
    }

    func stop() {
        generation = UUID(); readyURL = nil; callbacks.removeAll()
        timeout?.cancel(); timeout = nil
        output?.fileHandleForReading.readabilityHandler = nil
        if let process, process.isRunning { process.terminate() }
        process = nil; output = nil
    }
    deinit { stop() }
}

