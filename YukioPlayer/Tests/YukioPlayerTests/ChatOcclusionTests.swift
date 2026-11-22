import CoreGraphics
import YukioCore
import Testing
@testable import YukioPlayer

/// Window list recorded on a real two-display Mac (built-in 1512×982, external above it)
/// where the completion sign never went down for chats on the built-in display.
@Suite struct ChatOcclusionTests {
    let builtIn = CGRect(x: 0, y: 0, width: 1512, height: 982)
    let external = CGRect(x: -209, y: -1080, width: 1920, height: 1080)

    private func window(_ id: Int, pid: pid_t, layer: Int, _ bounds: CGRect, dock: Bool = false) -> BrowserOpenChat.Window {
        // Same classification as Snapshot.capture().
        BrowserOpenChat.Window(id: id, pid: pid, bounds: bounds, layer: layer,
            isDesktopOverlay: ChatWindowVisibility.isSystemOverlay(layer: layer)
                || ChatWindowVisibility.isDesktopOverlay(isDock: dock, layer: layer, bounds: bounds, screens: [builtIn, external]))
    }

    /// Front-to-back: menu bar, the screenshot tool's lingering display-sized surface,
    /// the Dock's display-sized surface, then whatever the test puts in front of the chat.
    private func snapshot(inFront: [BrowserOpenChat.Window] = [], chat: BrowserOpenChat.Window,
                          screens: [CGRect]? = nil) -> BrowserOpenChat.Snapshot {
        BrowserOpenChat.Snapshot(windows: [
            window(4242, pid: 616, layer: 24, CGRect(x: 0, y: 0, width: 1512, height: 33)),
            window(3517, pid: 38338, layer: 24, builtIn),
            window(55, pid: 1296, layer: 20, builtIn, dock: true),
        ] + inFront + [chat], screens: screens ?? [builtIn, external])
    }

    @Test func chatOnBuiltInDisplayIsReadableUnderSystemOverlays() {
        let chat = window(900, pid: 1290, layer: 0, CGRect(x: 100, y: 60, width: 1200, height: 800))
        let seen = snapshot(chat: chat)
        #expect(seen.readable(chat.bounds.insetBy(dx: 20, dy: 50), in: chat))
        #expect(seen.visibleSingleWindow(pid: 1290))
        // A notification banner or pop-up menu in front changes nothing either.
        let banner = window(901, pid: 1156, layer: 23, CGRect(x: 1150, y: 40, width: 350, height: 90))
        let menu = window(902, pid: 1290, layer: 101, CGRect(x: 300, y: 200, width: 260, height: 400))
        #expect(snapshot(inFront: [banner, menu], chat: chat).readable(chat.bounds.insetBy(dx: 20, dy: 50), in: chat))
    }

    @Test func ordinaryWindowsLockScreenAndSleepingDisplayStillHideTheChat() {
        let chat = window(900, pid: 1290, layer: 0, CGRect(x: 100, y: 60, width: 1200, height: 800))
        let inner = chat.bounds.insetBy(dx: 20, dy: 50)
        let browser = window(910, pid: 1286, layer: 0, builtIn)
        #expect(!snapshot(inFront: [browser], chat: chat).readable(inner, in: chat))
        let floating = window(911, pid: 1293, layer: 3, builtIn)
        #expect(!snapshot(inFront: [floating], chat: chat).readable(inner, in: chat))
        let lockScreen = window(912, pid: 400, layer: 2_147_483_628, builtIn)
        #expect(!snapshot(inFront: [lockScreen], chat: chat).readable(inner, in: chat))
        let screenSaver = window(913, pid: 401, layer: 1000, builtIn)
        #expect(!snapshot(inFront: [screenSaver], chat: chat).readable(inner, in: chat))
        // capture() drops sleeping displays and, when the session is locked, every display.
        #expect(!snapshot(chat: chat, screens: [external]).readable(inner, in: chat))
        #expect(!snapshot(chat: chat, screens: []).readable(inner, in: chat))
    }

    @Test func overlaysComingAndGoingDoNotInvalidateAScan() {
        let chat = window(900, pid: 1290, layer: 0, CGRect(x: 100, y: 60, width: 1200, height: 800))
        let before = snapshot(chat: chat)
        let banner = window(901, pid: 1156, layer: 23, CGRect(x: 1150, y: 40, width: 350, height: 90))
        #expect(snapshot(inFront: [banner], chat: chat).sameContent(as: before))
        // A moved chat window, a new ordinary window or a display change still invalidates it.
        let moved = window(900, pid: 1290, layer: 0, CGRect(x: 140, y: 60, width: 1200, height: 800))
        #expect(!snapshot(chat: moved).sameContent(as: before))
        let browser = window(910, pid: 1286, layer: 0, CGRect(x: 0, y: 40, width: 700, height: 600))
        #expect(!snapshot(inFront: [browser], chat: chat).sameContent(as: before))
        #expect(!snapshot(chat: chat, screens: [builtIn]).sameContent(as: before))
    }
}
