import AppKit
import Testing
import YukioCore
@testable import YukioPlayer

@Suite @MainActor struct ChatCardVisibilityTests {
    @Test func multipleChatsUseVisibleAndExpandableWindows() throws {
        _ = NSApplication.shared
        let root = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent("Resources/Assets")
        let catalog = try AnimationCatalog.load(assetsRoot: root)
        let library = try SpriteLibrary(catalog: catalog, assetsRoot: root)
        let suite = "local.yukio.chat-card-tests." + UUID().uuidString
        let defaults = try #require(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        let controller = AppController(catalog: catalog, library: library, defaults: defaults)
        for (name, passed) in controller.chatCardsForCheck().sorted(by: { $0.key < $1.key }) {
            #expect(passed, "\(name)")
        }
    }
}
