import AppKit
import WebKit
import YukioCore

/// Opt-in native integration check. Uses a real AppKit event loop and an empty
/// test page, never a real conversation or model request.
func runWorkbenchPanelCheck(path: String) {
    let arguments = CommandLine.arguments
    if let i = arguments.firstIndex(of: "--workbench-check-resources"), i + 1 < arguments.count,
       let j = arguments.firstIndex(of: "--workbench-check-data"), j + 1 < arguments.count {
        runWorkbenchConnectionCheck(path: path, resources: URL(fileURLWithPath: arguments[i + 1]),
                                    directory: URL(fileURLWithPath: arguments[j + 1]))
        return
    }
    final class CheckRuntime: WorkbenchStarting {
        var starts = 0, stops = 0
        func start(_ completion: @escaping (Result<URL, Error>) -> Void) {
            starts += 1
            completion(.success(URL(string: "http://127.0.0.1:8767/native-check-empty")!))
        }
        func stop() { stops += 1 }
    }
    let app = NSApplication.shared
    app.setActivationPolicy(.accessory)
    let runtime = CheckRuntime()
    let controller = WorkbenchPanelController(runtime: runtime)
    let snapshot = SettingsSnapshot(status: "独立窗口检查", following: true, hidden: false, provider: .auto,
        chats: [], showBubble: true, showCards: true, showQuestionCard: true, scale: 1, language: .chinese, demoPlaying: false)
    var results: [String: Bool] = [:]
    controller.show(snapshot: snapshot, near: .zero)
    DispatchQueue.main.asyncAfter(deadline: .now() + 1) {
        results["workbench_in_app"] = controller.webView?.window === controller.window
        controller.showSettings()
        results["settings_in_same_window"] = controller.settings.embeddedView().window === controller.window
        controller.showWork()
        results["return_to_same_page"] = runtime.starts == 1 && controller.webView?.window === controller.window
        controller.close()
        results["close_discards_page"] = controller.webView == nil && controller.window?.isVisible == false
        results["close_keeps_recorder"] = runtime.stops == 0
        controller.show(snapshot: snapshot, near: .zero)
        results["reopen_creates_page"] = runtime.starts == 2 && controller.webView != nil
        DispatchQueue.main.asyncAfter(deadline: .now() + 1) {
            controller.shutdown(); controller.close()
            results["quit_stops_owned_launcher"] = runtime.stops == 1 && controller.webView == nil
            if let data = try? JSONSerialization.data(withJSONObject: results, options: [.prettyPrinted, .sortedKeys]) {
                try? data.write(to: URL(fileURLWithPath: path), options: .atomic)
            }
            // NSApplication.stop may wait for another UI event before run()
            // returns. This explicit CLI check has finished and owns no work;
            // exit here so unattended verification cannot wait indefinitely.
            exit(results.count == 7 && results.values.allSatisfy { $0 } ? 0 : 1)
        }
    }
    withExtendedLifetime(controller) { app.run() }
    exit(results.count == 7 && results.values.allSatisfy { $0 } ? 0 : 1)
}

/// Explicit, isolated package check: use only a new empty profile and synthetic
/// sources, then verify the real native host loads the actual selected service.
private func runWorkbenchConnectionCheck(path: String, resources: URL, directory: URL) {
    guard !FileManager.default.fileExists(atPath: directory.path) else { exit(2) }
    let sources = directory.appendingPathComponent("sources")
    do {
        for client in ["codex", "claude", "deepcode"] {
            try FileManager.default.createDirectory(at: sources.appendingPathComponent(client), withIntermediateDirectories: true)
        }
    } catch { exit(2) }
    let runtime = WorkbenchRuntime(resources: resources, launchArguments: ["--collect", "--no-browser", "--port", "0",
        "--data-dir", directory.appendingPathComponent("data").path, "--source-root", sources.path])
    let app = NSApplication.shared
    app.setActivationPolicy(.accessory)
    let controller = WorkbenchPanelController(runtime: runtime, preferredLanguages: ["en"])
    let snapshot = SettingsSnapshot(status: "Isolated connection check", following: true, hidden: false, provider: .auto,
        chats: [], showBubble: true, showCards: true, showQuestionCard: true, scale: 1, language: .english, demoPlaying: false)
    controller.show(snapshot: snapshot, near: .zero)
    let deadline = Date().addingTimeInterval(20)
    var finished = false
    func finish(_ report: [String: Any], success: Bool) {
        guard !finished else { return }; finished = true
        if let data = try? JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys]) {
            try? data.write(to: URL(fileURLWithPath: path), options: .atomic)
        }
        controller.shutdown(); controller.close()
        DispatchQueue.main.asyncAfter(deadline: .now() + 1) { exit(success ? 0 : 1) }
    }
    func poll() {
        guard !finished else { return }
        if Date() > deadline { finish(["connected": false, "diagnostic": controller.diagnosticText], success: false); return }
        guard let web = controller.webView else { DispatchQueue.main.asyncAfter(deadline: .now() + 0.1, execute: poll); return }
        web.evaluateJavaScript("document.readyState === 'complete' && !!document.querySelector('#chatLists') && !!document.querySelector('#connection')") { result, _ in
            guard result as? Bool == true, let url = web.url, let port = controller.serviceURL?.port,
                  WorkbenchPanelController.isLocal(url, port: port) else {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.1, execute: poll); return
            }
            // Confirm the page's API as well as HTML at the dynamically chosen origin.
            web.evaluateJavaScript("fetch('/api/clients', {headers: {'X-Yukio-Workbench':'1'}}).then(r => {document.body.dataset.connectionCheck = r.ok ? 'ok' : 'failed';}).catch(() => {document.body.dataset.connectionCheck='failed';}); 0") { _, _ in
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                    web.evaluateJavaScript("document.body.dataset.connectionCheck") { state, _ in
                        let connected = state as? String == "ok"
                        controller.showSettings(); controller.showWork()
                        let samePage = controller.webView === web
                        web.takeSnapshot(with: nil) { image, _ in
                            if let tiff = image?.tiffRepresentation, let bitmap = NSBitmapImageRep(data: tiff),
                               let png = bitmap.representation(using: .png, properties: [:]) {
                                try? png.write(to: URL(fileURLWithPath: path).deletingPathExtension().appendingPathExtension("png"))
                            }
                            finish(["connected": connected, "actual_port": port, "page_port": url.port ?? 0,
                                    "native_page_loaded": true, "settings_returned_to_same_page": samePage,
                                    "isolated_profile": true], success: connected && samePage)
                        }
                    }
                }
            }
        }
    }
    DispatchQueue.main.asyncAfter(deadline: .now() + 0.1, execute: poll)
    withExtendedLifetime(controller) { app.run() }
}
