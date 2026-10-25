import AppKit
import WebKit
import YukioCore

/// Opt-in native integration check. Uses a real AppKit event loop and an empty
/// test page, never a real conversation or model request.
func runWorkbenchPanelCheck(path: String) {
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
            app.stop(nil)
            CFRunLoopStop(CFRunLoopGetMain())
        }
    }
    withExtendedLifetime(controller) { app.run() }
    exit(results.count == 7 && results.values.allSatisfy { $0 } ? 0 : 1)
}
