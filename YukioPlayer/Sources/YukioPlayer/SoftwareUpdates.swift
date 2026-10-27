import AppKit
import Sparkle
import YukioCore

/// Sparkle checks the signed feed and filters versions/compatibility. Offers only
/// open the official download page; this driver never authorizes installation.
final class YukioUpdateDriver: SPUStandardUserDriver {
    var presentNotice: (NSAlert) -> NSApplication.ModalResponse = { $0.runModal() }
    var openPage: (URL) -> Bool = { NSWorkspace.shared.open($0) }

    static let downloads = URL(string: "https://github.com/leozhang8654/yukio-desktop-pet/releases/latest")!

    static func downloadPage(_ candidate: URL?) -> URL {
        guard let candidate,
              let parts = URLComponents(url: candidate, resolvingAgainstBaseURL: false),
              parts.scheme == "https", parts.host == "github.com",
              parts.user == nil, parts.password == nil, parts.port == nil,
              parts.query == nil, parts.fragment == nil,
              parts.path.range(of: #"^/leozhang8654/yukio-desktop-pet/releases/tag/v[0-9]+\.[0-9]+\.[0-9]+$"#,
                               options: .regularExpression) != nil else { return downloads }
        return candidate
    }

    override func showUpdateFound(with appcastItem: SUAppcastItem, state: SPUUserUpdateState,
                                  reply: @escaping (SPUUserUpdateChoice) -> Void) {
        offer(version: appcastItem.displayVersionString, page: appcastItem.infoURL,
              alreadyInstalling: state.stage == .installing, reply: reply)
    }

    func offer(version: String, page: URL?, alreadyInstalling: Bool = false,
               reply: (SPUUserUpdateChoice) -> Void) {
        // End Sparkle's cycle before presenting our manual-download notice. Skip
        // also cancels an old staged installation; dismiss alone would retain it.
        reply(alreadyInstalling ? .skip : .dismiss)
        let alert = NSAlert()
        alert.messageText = tr("Yukio %@ is available", "发现新版本 Yukio %@")
            .replacingOccurrences(of: "%@", with: version)
        alert.informativeText = tr(
            "Open the official download page, download the complete Mac app, then quit Yukio and replace your current copy in the same location. Your chats and settings are kept separately. Yukio will not download, install or restart itself.",
            "打开官方下载页，下载完整 Mac 版本，然后退出雪绪，在原位置替换现有程序。聊天记录和设置单独保存。雪绪不会自行下载、安装或重启。")
        alert.addButton(withTitle: tr("Open download page", "打开下载页"))
        alert.addButton(withTitle: tr("Later", "稍后再说"))
        if presentNotice(alert) == .alertFirstButtonReturn,
           !openPage(Self.downloadPage(page)) {
            let failed = NSAlert()
            failed.messageText = tr("Couldn’t open the download page", "未能打开下载页")
            failed.informativeText = tr(
                "Your current app is unchanged. Try again later, or open Yukio’s releases on GitHub.",
                "当前程序没有改变。请稍后重试，或在 GitHub 打开 Yukio 的版本发布页。")
            failed.addButton(withTitle: tr("OK", "好"))
            _ = presentNotice(failed)
        }
    }

    // Defensive handling of a previously staged update. No callback can approve
    // download, extraction, application exit, replacement or relaunch.
    override func showDownloadInitiated(cancellation: @escaping () -> Void) { cancellation() }
    override func showReady(toInstallAndRelaunch reply: @escaping (SPUUserUpdateChoice) -> Void) { reply(.skip) }
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
