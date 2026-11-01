import AppKit
import Sparkle
import YukioCore

struct UpdateFailureMessage {
    let title: String
    let detail: String
    let button: String

    init(_ error: NSError, language: UILanguage) {
        func text(_ en: String, _ zh: String) -> String { tr(en, zh, in: language) }
        title = text("Could not update Yukio", "未能更新雪绪")
        button = text("Close", "关闭")
        var reason: String
        if error.domain == SUSparkleErrorDomain {
            switch error.code {
            case 1000, 1002:
                reason = text("The update list could not be loaded. The update service may be unavailable. Try again later; this does not mean you have the latest version.", "无法读取更新列表，更新服务可能暂时不可用。请稍后重试；这不代表当前已是最新版。")
            case 1003, 1005, 4012:
                reason = text("Yukio cannot update in its current location. Quit it, copy the app to Applications, then open that copy and try again.", "当前位置无法更新。请退出雪绪，将 App 复制到“应用程序”，再从那里打开并重试。")
            case 2001:
                reason = text("The update could not be downloaded. Check your connection and try again. Your installed app is unchanged.", "更新包下载失败。请检查网络后重试，当前安装的 App 未被替换。")
            case 3000, 3001, 3002, 4009:
                reason = text("The update package could not be verified or opened. Do not bypass this check. Retry later or use a verified release from the project.", "更新包无法验证或解包。请勿绕过检查；可稍后重试，或使用项目提供的已核验发行包。")
            default:
                reason = text("The update did not finish. Keep your current app and data, and include the error code below when reporting the problem.", "更新未完成。请保留当前 App 和资料，反馈问题时附上下面的错误编号。")
            }
        } else {
            reason = text("The update did not finish. Check your connection and retry; include the error code below if it continues.", "更新未完成。请检查网络后重试；若仍失败，反馈时附上下面的错误编号。")
        }
        // Never display raw underlying descriptions: they may contain URLs, tokens or paths.
        var codes = [String(error.code)]
        var underlying = error.userInfo[NSUnderlyingErrorKey] as? NSError
        for _ in 0..<4 {
            guard let item = underlying else { break }
            codes.append(String(item.code))
            if item.domain == NSURLErrorDomain {
                if item.code == NSURLErrorNotConnectedToInternet {
                    reason = text("There is no internet connection. Reconnect and check for updates again.", "当前没有网络连接。联网后请重新检查更新。")
                } else if item.code == NSURLErrorTimedOut {
                    reason = text("The update request timed out. Check your connection and retry later.", "更新请求超时。请检查网络，稍后重试。")
                }
            }
            underlying = item.userInfo[NSUnderlyingErrorKey] as? NSError
        }
        detail = reason + "\n\n" + text("Error code: ", "错误编号：") + codes.joined(separator: " / ")
    }
}

/// A user-approved update downloads, installs and relaunches through Sparkle.
/// Background checks alone never authorize download or installation.
final class YukioUpdateDriver: SPUStandardUserDriver {
    private(set) var installWasRequested = false

    override func showUpdaterError(_ error: Error, acknowledgement: @escaping () -> Void) {
        // Use the app's current language, including a language change since launch.
        // Public teardown closes Sparkle's checking/download windows before our alert.
        super.dismissUpdateInstallation()
        installWasRequested = false
        let message = UpdateFailureMessage(error as NSError, language: L10n.language)
        let alert = NSAlert()
        alert.messageText = message.title
        alert.informativeText = message.detail
        alert.addButton(withTitle: message.button)
        alert.runModal()
        acknowledgement()
    }

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
final class SoftwareUpdates: NSObject, SPUStandardUserDriverDelegate {
    private var updater: SPUUpdater?
    private var driver: YukioUpdateDriver?
    weak var settingsWindow: NSWindow?
    private weak var loweredWindow: NSWindow?
    private var originalLevel: NSWindow.Level?

    func prepareManualPresentation() {
        guard loweredWindow == nil, let window = settingsWindow, window.isVisible else { return }
        loweredWindow = window
        originalLevel = window.level
        window.level = .normal
    }

    func standardUserDriverWillFinishUpdateSession() {
        if let window = loweredWindow, let level = originalLevel { window.level = level }
        loweredWindow = nil
        originalLevel = nil
    }

    var automaticallyChecks: Bool {
        get { updater?.automaticallyChecksForUpdates ?? true }
        set { updater?.automaticallyChecksForUpdates = newValue }
    }

    func start() {
        guard Bundle.main.bundleURL.pathExtension == "app",
              Bundle.main.object(forInfoDictionaryKey: "SUFeedURL") != nil else { return }
        let driver = YukioUpdateDriver(hostBundle: .main, delegate: self)
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
        prepareManualPresentation()
        updater.checkForUpdates()
    }
}
