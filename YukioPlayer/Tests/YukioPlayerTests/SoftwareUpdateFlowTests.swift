import AppKit
import Sparkle
import Testing
@testable import YukioPlayer

@Suite @MainActor struct SoftwareUpdateFlowTests {
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
