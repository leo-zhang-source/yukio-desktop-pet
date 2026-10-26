import AppKit
import Sparkle
import YukioCore

/// Sparkle verifies signed archives and performs the quit/replace/relaunch handoff.
/// No updater runs in command-line checks, tests, or unbundled development builds.
final class SoftwareUpdates: NSObject {
    private var updater: SPUUpdater?
    private var driver: SPUStandardUserDriver?

    var automaticallyChecks: Bool {
        get { updater?.automaticallyChecksForUpdates ?? true }
        set { updater?.automaticallyChecksForUpdates = newValue }
    }

    func start() {
        guard Bundle.main.bundleURL.pathExtension == "app",
              Bundle.main.object(forInfoDictionaryKey: "SUFeedURL") != nil else { return }
        let driver = SPUStandardUserDriver(hostBundle: .main, delegate: nil)
        let updater = SPUUpdater(hostBundle: .main, applicationBundle: .main, userDriver: driver, delegate: nil)
        self.driver = driver
        self.updater = updater
        do { try updater.start() }
        catch { NSLog("Yukio updater could not start: %@", error.localizedDescription) }
        // Sparkle owns subsequent scheduling and honours the user's saved preference.
        DispatchQueue.main.asyncAfter(deadline: .now() + 15) { [weak self] in
            guard let updater = self?.updater,
                  updater.automaticallyChecksForUpdates, updater.canCheckForUpdates,
                  Date().timeIntervalSince(updater.lastUpdateCheckDate ?? .distantPast) >= 21600 else { return }
            updater.checkForUpdatesInBackground()
        }
    }

    @objc func checkForUpdates(_ sender: Any? = nil) {
        guard let updater else {
            let alert = NSAlert()
            alert.messageText = tr("Updates are available in the installed app", "请在已安装的雪绪中检查更新")
            alert.informativeText = tr("Open Yukio.app and try again.", "打开 Yukio.app 后重试。")
            alert.runModal()
            return
        }
        updater.checkForUpdates()
    }
}
