import AppKit
import Sparkle
import Testing
import YukioCore
@testable import YukioPlayer

@Suite @MainActor struct SoftwareUpdateFlowTests {
    @Test func setupLinksAreExactPublicDocumentationOnly() {
        #expect(WorkbenchPanelController.isSetupDocumentation(URL(string: "https://code.claude.com/docs/en/setup")!))
        for value in ["https://code.claude.com/docs/en/setup?token=private", "https://code.claude.com.evil.test/docs/en/setup", "file:///tmp/setup", "https://developers.openai.com/codex/cli#private"] {
            #expect(!WorkbenchPanelController.isSetupDocumentation(URL(string: value)!))
        }
    }

    @Test func manualCheckLowersOnlyItsSettingsAndRestoresAfterEverySession() {
        _ = NSApplication.shared
        let settings = NSPanel(contentRect: .zero, styleMask: [.titled], backing: .buffered, defer: false)
        let unrelated = NSPanel(contentRect: .zero, styleMask: [.titled], backing: .buffered, defer: false)
        settings.level = .floating
        unrelated.level = .floating
        settings.orderBack(nil)
        defer { settings.orderOut(nil) }
        let updates = SoftwareUpdates()
        updates.settingsWindow = settings
        #expect(settings.level == .floating) // Background checks do not prepare manual presentation.
        for _ in 0..<3 {
            updates.prepareManualPresentation()
            updates.prepareManualPresentation() // Clicking again must not overwrite the original level.
            #expect(settings.level == .normal)
            #expect(unrelated.level == .floating)
            updates.standardUserDriverWillFinishUpdateSession()
            updates.standardUserDriverWillFinishUpdateSession()
            #expect(settings.level == .floating)
        }
    }

    @Test func updateErrorsUseSelectedLanguageAndPreserveSafeReasonCodes() {
        let nested = NSError(domain: NSURLErrorDomain, code: NSURLErrorTimedOut,
                             userInfo: [NSLocalizedDescriptionKey: "private-token-and-path"])
        let error = NSError(domain: SUSparkleErrorDomain, code: 1002,
                            userInfo: [NSUnderlyingErrorKey: nested])
        let chinese = UpdateFailureMessage(error, language: .chinese)
        let english = UpdateFailureMessage(error, language: .english)
        #expect(chinese.detail.contains("超时"))
        #expect(english.detail.contains("timed out"))
        #expect(chinese.button == "关闭")
        #expect(english.button == "Close")
        #expect(chinese.detail.contains("1002 / -1001"))
        #expect(!english.detail.contains("private-token-and-path"))
        #expect(UpdateFailureMessage(NSError(domain: SUSparkleErrorDomain, code: 3001), language: .chinese).detail.contains("勿绕过"))
        #expect(UpdateFailureMessage(NSError(domain: SUSparkleErrorDomain, code: 1003), language: .english).detail.contains("Applications"))
    }

    private func driver() -> YukioUpdateDriver {
        _ = NSApplication.shared
        return YukioUpdateDriver(hostBundle: .main, delegate: nil)
    }

    @Test func backgroundCheckDoesNotAuthorizeInstallation() {
        let driver = driver()
        #expect(!driver.consumeInstallRequest())
        #expect(!driver.consumeInstallRequest())
    }

    @Test func explicitInstallClickAuthorizesOnlyOneInstallCycle() {
        let driver = driver()
        #expect(driver.recordUserChoice(.install) == .install)
        var choice: SPUUserUpdateChoice?
        driver.showReady(toInstallAndRelaunch: { choice = $0 })
        #expect(choice == .install)
        #expect(!driver.consumeInstallRequest())
    }

    @Test func laterAndSkipClearAnyPreviousConsent() {
        let driver = driver()
        for choice in [SPUUserUpdateChoice.dismiss, .skip] {
            _ = driver.recordUserChoice(.install)
            #expect(driver.recordUserChoice(choice) == choice)
            #expect(!driver.consumeInstallRequest())
        }
    }

    @Test func informationalFallbackCannotAuthorizeAnInstaller() {
        let driver = driver()
        #expect(driver.recordUserChoice(.install, informational: true) == .dismiss)
        #expect(!driver.consumeInstallRequest())
    }
}
