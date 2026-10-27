import AppKit
import Sparkle
import YukioCore

/// A user-approved update downloads, installs and relaunches through Sparkle.
/// Background checks alone never authorize download or installation.
final class YukioUpdateDriver: SPUStandardUserDriver {
    private(set) var installWasRequested = false

    func recordUserChoice(_ choice: SPUUserUpdateChoice, informational: Bool = false) -> SPUUserUpdateChoice {
        let accepted: SPUUserUpdateChoice = informational && choice == .install ? .dismiss : choice
        installWasRequested = accepted == .install
        return accepted
    }

    func consumeInstallRequest() -> Bool {
        let requested = installWasRequested
        installWasRequested = false
        return requested
    }

    override func showUpdateFound(with appcastItem: SUAppcastItem, state: SPUUserUpdateState,
                                  reply: @escaping (SPUUserUpdateChoice) -> Void) {
        installWasRequested = false
        super.showUpdateFound(with: appcastItem, state: state) { [weak self] choice in
            let accepted = self?.recordUserChoice(choice, informational: appcastItem.isInformationOnlyUpdate) ?? .dismiss
            reply(accepted)
        }
    }

    override func showReady(toInstallAndRelaunch reply: @escaping (SPUUserUpdateChoice) -> Void) {
        // The initial Install Update click authorizes this download/install cycle.
        // A previously staged update without that click keeps Sparkle's confirmation.
        if consumeInstallRequest() { reply(.install) }
        else { super.showReady(toInstallAndRelaunch: reply) }
    }
}

/// No updater runs in command-line checks, tests or unbundled development builds.
final class SoftwareUpdates: NSObject {
    private var updater: SPUUpdater?
    private var driver: YukioUpdateDriver?

    var automaticallyChecks: Bool {
        get { updater?.automaticallyChecksForUpdates ?? true }
        set { updater?.automaticallyChecksForUpdates = newValue }
    }

    func start() {
        guard Bundle.main.bundleURL.pathExtension == "app",
              Bundle.main.object(forInfoDictionaryKey: "SUFeedURL") != nil else { return }
        let driver = YukioUpdateDriver(hostBundle: .main, delegate: nil)
        let updater = SPUUpdater(hostBundle: .main, applicationBundle: .main, userDriver: driver, delegate: nil)
        self.driver = driver
        self.updater = updater
        do { try updater.start() }
        catch { NSLog("Yukio updater could not start: %@", error.localizedDescription) }
        // Sparkle owns subsequent scheduling and honours the saved opt-out.
        // SUAllowsAutomaticUpdates=false disables downloads even for an old opt-in.
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
            alert.informativeText = tr("Open Yukio and try again.", "打开雪绪后重试。")
            alert.runModal()
            return
        }
        updater.checkForUpdates()
    }
}
