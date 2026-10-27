import AppKit
import Sparkle
import Testing
import YukioCore
@testable import YukioPlayer

@Suite(.serialized) @MainActor struct ManualUpdateTests {
    @Test func acceptsOnlyTheOfficialReleasePage() {
        let allowed = URL(string: "https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.4.13")!
        #expect(YukioUpdateDriver.downloadPage(allowed) == allowed)
        for raw in ["http://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.4.13",
                    "https://github.com.evil.test/leozhang8654/yukio-desktop-pet/releases/tag/v0.4.13",
                    "https://github.com/another/project/releases/tag/v0.4.13",
                    "https://user@github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.4.13",
                    "https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.4.13?token=private",
                    "file:///tmp/update", "https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/../../evil"] {
            #expect(YukioUpdateDriver.downloadPage(URL(string: raw)) == YukioUpdateDriver.downloads)
        }
        #expect(YukioUpdateDriver.downloadPage(nil) == YukioUpdateDriver.downloads)
    }

    @Test func noticeOffersManualDownloadInBothLanguagesAndNeverInstalls() {
        _ = NSApplication.shared
        let saved = L10n.language
        defer { L10n.language = saved }
        for language in [UILanguage.english, .chinese] {
            L10n.language = language
            let driver = YukioUpdateDriver(hostBundle: .main, delegate: nil)
            var choices: [SPUUserUpdateChoice] = []
            var opened: [URL] = []
            driver.openPage = { opened.append($0); return true }
            driver.presentNotice = { alert in
                #expect(alert.messageText.contains("0.4.13"))
                #expect(alert.buttons.map(\.title) == (language == .english ? ["Open download page", "Later"] : ["打开下载页", "稍后再说"]))
                #expect(alert.informativeText.contains(language == .english ? "will not download, install or restart itself" : "不会自行下载、安装或重启"))
                return .alertFirstButtonReturn
            }
            driver.offer(version: "0.4.13", page: nil) { choices.append($0) }
            #expect(choices == [.dismiss])
            #expect(opened == [YukioUpdateDriver.downloads])
        }
    }

    @Test func laterLeavesCurrentAppRunningAndDoesNotOpenTheBrowser() {
        _ = NSApplication.shared
        let driver = YukioUpdateDriver(hostBundle: .main, delegate: nil)
        driver.presentNotice = { _ in .alertSecondButtonReturn }
        driver.openPage = { _ in Issue.record("Later must not open a page"); return false }
        var choice: SPUUserUpdateChoice?
        driver.offer(version: "0.4.13", page: nil) { choice = $0 }
        #expect(choice == .dismiss)
    }

    @Test func oldStagedInstallerAndUnexpectedDownloadAreCancelled() {
        _ = NSApplication.shared
        let driver = YukioUpdateDriver(hostBundle: .main, delegate: nil)
        driver.presentNotice = { _ in .alertSecondButtonReturn }
        var choices: [SPUUserUpdateChoice] = []
        driver.offer(version: "0.4.13", page: nil, alreadyInstalling: true) { choices.append($0) }
        driver.showReady(toInstallAndRelaunch: { choices.append($0) })
        var cancelled = false
        driver.showDownloadInitiated(cancellation: { cancelled = true })
        #expect(choices == [.skip, .skip])
        #expect(cancelled)
    }

    @Test func browserFailureIsExplainedWithoutTryingAnInstaller() {
        _ = NSApplication.shared
        let driver = YukioUpdateDriver(hostBundle: .main, delegate: nil)
        var notices: [NSAlert] = []
        var choices: [SPUUserUpdateChoice] = []
        driver.presentNotice = { notices.append($0); return .alertFirstButtonReturn }
        driver.openPage = { _ in false }
        driver.offer(version: "0.4.13", page: nil) { choices.append($0) }
        #expect(notices.count == 2)
        #expect(choices == [.dismiss])
        #expect(notices[1].buttons.count == 1)
    }
}
