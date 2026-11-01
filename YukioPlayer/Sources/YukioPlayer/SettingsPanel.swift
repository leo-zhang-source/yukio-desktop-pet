import AppKit
import YukioCore

/// 设置面板使用文字、系统控件和醒目的取消举牌图标。
struct SettingsSnapshot {
    let status: String
    let following: Bool
    let hidden: Bool
    let provider: AgentProvider
    let chats: [SessionSummary]
    let showBubble: Bool
    let showCards: Bool
    let showQuestionCard: Bool
    let scale: CGFloat
    let language: UILanguage
    let demoPlaying: Bool
    var launchAtLogin: LaunchAtLoginStatus = .disabled
    var automaticUpdates: Bool = true
    var hideWhenIdle: Bool = true
    var skin: PetSkin = .yukio
    var englishStatus: String? = nil
}

enum SettingsChange {
    case skin(PetSkin)
    case hideWhenIdle(Bool)
    case quit
    case checkForUpdates
    case automaticUpdates(Bool)
    case following(Bool)
    case launchAtLogin(Bool)
    case openLoginItems
    case provider(AgentProvider)
    case chat(String?)
    case showBubble(Bool)
    case showCards(Bool)
    case showQuestionCard(Bool)
    case scale(CGFloat)
    case language(UILanguage)
    case toggleHidden
    case resetPosition
    case toggleDemo
    case lowerSign
    case browserChatPermission
}

final class SettingsPanelController: NSWindowController, NSWindowDelegate, NSMenuDelegate {
    var onChange: ((SettingsChange) -> Void)?
    var presentationLanguage: UILanguage?
    private var labelLanguage: UILanguage = .english
    private func tr(_ en: String, _ zh: String) -> String { labelLanguage == .chinese ? zh : en }

    private let outsideClickMonitor = SettingsOutsideClickMonitor()

    private final class ContentView: NSView {
        var onLayout: (() -> Void)?
        override var isFlipped: Bool { true }
        override func layout() {
            super.layout()
            onLayout?()
        }
    }
    private let root = ContentView()
    var onEmbeddedDone: (() -> Void)?
    var isTrackingPopup: Bool { trackingPopupMenu }
    private var viewportConstraints: [NSLayoutConstraint] = []

    func embeddedView() -> NSView { root }

    func embed(in scrollView: NSScrollView) {
        window?.contentView = nil
        configureScrollView(scrollView)
    }

    private func configureScrollView(_ scrollView: NSScrollView) {
        NSLayoutConstraint.deactivate(viewportConstraints)
        root.removeFromSuperview()
        scrollView.documentView = root
        scrollView.hasVerticalScroller = true
        scrollView.hasHorizontalScroller = false
        scrollView.autohidesScrollers = true
        scrollView.drawsBackground = true
        scrollView.backgroundColor = NSColor(calibratedWhite: 0.965, alpha: 1)
        let fillHeight = root.heightAnchor.constraint(equalTo: scrollView.contentView.heightAnchor)
        fillHeight.priority = .defaultLow
        viewportConstraints = [
            root.widthAnchor.constraint(equalTo: scrollView.contentView.widthAnchor),
            root.heightAnchor.constraint(greaterThanOrEqualTo: scrollView.contentView.heightAnchor),
            fillHeight,
        ]
        NSLayoutConstraint.activate(viewportConstraints)
    }
    private let stack = NSStackView()
    private let categoryHost = NSStackView()
    private var categoryPanes: [NSStackView] = []
    private var columnCount = 0

    private let brandLabel = NSTextField(labelWithString: "YUKIO")
    private let statusLabel = NSTextField(wrappingLabelWithString: "")

    private let followTitle = NSTextField(labelWithString: "")
    private let providerTitle = NSTextField(labelWithString: "")
    private let chatTitle = NSTextField(labelWithString: "")
    private let bubbleTitle = NSTextField(labelWithString: "")
    private let cardsTitle = NSTextField(labelWithString: "")
    private let idleHideTitle = NSTextField(labelWithString: "")
    private let idleHideSwitch = NSSwitch()
    private let questionTitle = NSTextField(labelWithString: "")
    private let skinTitle = NSTextField(labelWithString: "")
    private let skinPopup = NSPopUpButton()
    private let scaleTitle = NSTextField(labelWithString: "")
    private let startupTitle = NSTextField(labelWithString: "")
    private let startupSwitch = NSSwitch()
    private let startupHint = NSTextField(wrappingLabelWithString: "")
    private let loginItemsButton = NSButton()
    private let languageTitle = NSTextField(labelWithString: "")

    private let followSwitch = NSSwitch()
    private let providerPopup = NSPopUpButton()
    private let chatPopup = NSPopUpButton()
    private let bubbleSwitch = NSSwitch()
    private let cardsSwitch = NSSwitch()
    private let questionSwitch = NSSwitch()
    private let scaleSlider = NSSlider()
    private let scaleReadout = NSTextField(labelWithString: "100%")
    private let languagePopup = NSPopUpButton()
    private let hideButton = NSButton()
    private let resetButton = NSButton()
    private let demoButton = NSButton()
    private let doneButton = NSButton()
    private let quitButton = NSButton()
    private let updateButton = NSButton()
    private let updateTitle = NSTextField(labelWithString: "")
    private let updateSwitch = NSSwitch()
    private let lowerSignButton = NSButton()
    private let browserChatButton = NSButton()

    private let followingHeading = NSTextField(labelWithString: "")
    private let displayHeading = NSTextField(labelWithString: "")
    private let interfaceHeading = NSTextField(labelWithString: "")
    private var updating = false
    /// NSPopUpButton 展开时不能删改它的菜单项；否则 AppKit 的菜单跟踪循环会卡住。
    private var trackingPopupMenu = false
    private var pendingSnapshot: SettingsSnapshot?

    init() {
        let panel = NSPanel(
            contentRect: NSRect(x: 0, y: 0, width: 1100, height: 650),
            styleMask: [.titled, .closable, .resizable, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )
        panel.level = .floating
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.isReleasedWhenClosed = false
        panel.hidesOnDeactivate = false
        panel.isMovableByWindowBackground = true
        panel.appearance = NSAppearance(named: .aqua)
        panel.backgroundColor = NSColor(calibratedWhite: 0.965, alpha: 1)
        panel.minSize = NSSize(width: 540, height: 420)
        super.init(window: panel)
        panel.delegate = self
        buildUI()
    }

    required init?(coder: NSCoder) { fatalError("not used") }

    func show(snapshot: SettingsSnapshot, near anchor: NSRect) {
        apply(snapshot)
        position(near: anchor)
        // Keep the current app/Space in place. Activating Yukio here can switch
        // back to its desktop instead of showing settings over a full-screen app.
        showWindow(nil)
        window?.makeKeyAndOrderFront(nil)
        window?.orderFrontRegardless()
        if let window {
            outsideClickMonitor.start(window: window,
                isInteracting: { [weak self] in self?.trackingPopupMenu ?? false },
                dismiss: { [weak self] in self?.close() })
        }
    }

    override func close() {
        outsideClickMonitor.stop()
        super.close()
    }

    func windowWillClose(_ notification: Notification) {
        outsideClickMonitor.stop()
    }

    func apply(_ snapshot: SettingsSnapshot) {
        guard !trackingPopupMenu else {
            pendingSnapshot = snapshot
            return
        }
        updating = true
        defer { updating = false }

        let displayLanguage = presentationLanguage ?? snapshot.language
        refreshLabels(language: displayLanguage)
        statusLabel.stringValue = displayLanguage == .english
            ? (snapshot.englishStatus ?? (snapshot.language == .english ? snapshot.status : "Activity status unavailable")) : snapshot.status
        updateSwitch.state = snapshot.automaticUpdates ? .on : .off
        followSwitch.state = snapshot.following ? .on : .off
        idleHideSwitch.state = snapshot.hideWhenIdle ? .on : .off
        bubbleSwitch.state = snapshot.showBubble ? .on : .off
        cardsSwitch.state = snapshot.showCards ? .on : .off
        questionSwitch.state = snapshot.showQuestionCard ? .on : .off
        startupSwitch.state = snapshot.launchAtLogin.isRegistered ? .on : .off
        let needsApproval = snapshot.launchAtLogin == .requiresApproval
        startupHint.isHidden = !needsApproval
        loginItemsButton.isHidden = !needsApproval
        updateSettingsLayout()

        sync(skinPopup, items: PetSkin.allCases.map { ($0.name(chinese: displayLanguage == .chinese), $0.rawValue) })
        select(skinPopup, value: snapshot.skin.rawValue)

        sync(providerPopup, items: AgentProvider.allCases.map { ($0 == .auto ? tr("Auto (whoever is working)", "自动（谁在干活跟谁）") : $0.displayName, $0.rawValue) })
        select(providerPopup, value: snapshot.provider.rawValue)

        let chatItems = [(tr("Automatic", "自动选择"), "")]
            + snapshot.chats.map { (chatLabel($0, language: displayLanguage), $0.id) }
        sync(chatPopup, items: chatItems)
        if let pinned = snapshot.chats.first(where: \.pinned) {
            select(chatPopup, value: pinned.id)
        } else {
            select(chatPopup, value: "")
        }
        chatPopup.isEnabled = !snapshot.chats.isEmpty

        let snapped = ScaleSliderView.snap(Double(snapshot.scale))
        scaleSlider.doubleValue = snapped
        scaleReadout.stringValue = "\(Int((snapped * 100).rounded()))%"

        sync(languagePopup, items: [("English", UILanguage.english.rawValue),
                                    (tr("Chinese (Simplified)", "中文"), UILanguage.chinese.rawValue)])
        select(languagePopup, value: snapshot.language.rawValue)
        demoButton.title = snapshot.demoPlaying ? tr("Stop demo", "停止演示") : tr("Play demo", "播放演示")
        hideButton.title = snapshot.hidden ? tr("Show Yukio", "显示雪绪") : tr("Hide Yukio", "收起雪绪")
        updateSettingsLayout()
    }

    private func chatLabel(_ chat: SessionSummary, language: UILanguage) -> String {
        guard language == .english else { return chat.menuLabel }
        let title = chat.title?.trimmingCharacters(in: .whitespacesAndNewlines)
        let name = title?.isEmpty == false ? chat.name : "Unnamed chat"
        let status: String
        if chat.signYielded { status = "Holding the sign for you (stepped aside)" }
        else if chat.raisedSign || chat.state == .task_complete { status = "Holding the sign, click her" }
        else if chat.live { status = L10n.stateName(chat.state, in: .english) }
        else if chat.state == .respond { status = "Just answered" }
        else if chat.state == .failed { status = "Stopped on an error" }
        else {
            let seconds = Int(max(0, chat.quietMs) / 1000)
            status = seconds < 60 ? "just now" : seconds < 3600 ? "\(seconds / 60) min ago" : "\(seconds / 3600) h ago"
        }
        return "\(name) · \(status)"
    }

    /// 定时刷新时大多数选项没有变化，不要反复拆掉 AppKit 正在使用的 NSMenu。
    private func sync(_ popup: NSPopUpButton, items: [(title: String, value: String)]) {
        let unchanged = popup.itemArray.count == items.count
            && zip(popup.itemArray, items).allSatisfy { item, expected in
                item.title == expected.title && item.representedObject as? String == expected.value
            }
        guard !unchanged else { return }
        popup.removeAllItems()
        for item in items {
            popup.addItem(withTitle: item.title)
            popup.lastItem?.representedObject = item.value
        }
    }

    private func select(_ popup: NSPopUpButton, value: String) {
        guard popup.selectedItem?.representedObject as? String != value,
              let item = popup.itemArray.first(where: { $0.representedObject as? String == value }) else { return }
        popup.select(item)
    }

    private func buildUI() {
        guard let window else { return }
        let scrollView = NSScrollView(frame: NSRect(x: 0, y: 0, width: 1100, height: 650))
        window.contentView = scrollView
        root.translatesAutoresizingMaskIntoConstraints = false
        configureScrollView(scrollView)
        root.onLayout = { [weak self] in self?.updateSettingsLayout() }
        root.wantsLayer = true
        root.layer?.backgroundColor = NSColor(calibratedWhite: 0.965, alpha: 1).cgColor
        stack.setAccessibilityIdentifier("settingsContentStack")
        stack.orientation = .vertical; stack.alignment = .leading; stack.spacing = 18
        stack.translatesAutoresizingMaskIntoConstraints = false
        root.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: root.leadingAnchor, constant: 24),
            stack.trailingAnchor.constraint(equalTo: root.trailingAnchor, constant: -24),
            stack.topAnchor.constraint(equalTo: root.topAnchor, constant: 24),
            stack.bottomAnchor.constraint(lessThanOrEqualTo: root.bottomAnchor, constant: -24),
        ])
        brandLabel.font = .systemFont(ofSize: 23, weight: .semibold)
        brandLabel.textColor = .labelColor
        statusLabel.font = .systemFont(ofSize: 12); statusLabel.textColor = .secondaryLabelColor
        statusLabel.maximumNumberOfLines = 2
        statusLabel.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        let identity = NSStackView(views: [brandLabel, statusLabel])
        identity.orientation = .vertical; identity.alignment = .leading; identity.spacing = 7
        statusLabel.widthAnchor.constraint(equalTo: identity.widthAnchor).isActive = true
        stack.addArrangedSubview(identity)
        identity.widthAnchor.constraint(equalTo: stack.widthAnchor).isActive = true

        let sliderGroup = NSStackView(views: [scaleSlider, scaleReadout])
        sliderGroup.orientation = .horizontal; sliderGroup.alignment = .centerY; sliderGroup.spacing = 10
        scaleSlider.setContentHuggingPriority(.defaultLow, for: .horizontal)
        scaleSlider.widthAnchor.constraint(greaterThanOrEqualToConstant: 100).isActive = true
        scaleReadout.widthAnchor.constraint(equalToConstant: 46).isActive = true
        scaleReadout.alignment = .right
        scaleReadout.font = .monospacedDigitSystemFont(ofSize: 12, weight: .regular)
        scaleReadout.textColor = .secondaryLabelColor
        lowerSignButton.heightAnchor.constraint(equalToConstant: 64).isActive = true
        browserChatButton.bezelStyle = .rounded
        browserChatButton.target = self; browserChatButton.action = #selector(browserChatPermission)
        browserChatButton.setAccessibilityIdentifier("browserChatPermissionButton")
        startupHint.font = .systemFont(ofSize: 12); startupHint.textColor = .secondaryLabelColor
        startupHint.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        startupHint.setAccessibilityIdentifier("startupApprovalHint")
        let updateActions = NSStackView(views: [updateButton, NSView(), quitButton])
        updateActions.orientation = .horizontal; updateActions.alignment = .centerY
        categoryPanes = [
            settingsGroup(displayHeading, [row(title: skinTitle, control: skinPopup, stacked: true), row(title: scaleTitle, control: sliderGroup, stacked: true), row(title: idleHideTitle, control: idleHideSwitch), row(title: bubbleTitle, control: bubbleSwitch), lowerSignButton]),
            settingsGroup(followingHeading, [row(title: followTitle, control: followSwitch), row(title: providerTitle, control: providerPopup, stacked: true), row(title: chatTitle, control: chatPopup, stacked: true), row(title: cardsTitle, control: cardsSwitch), row(title: questionTitle, control: questionSwitch), browserChatButton]),
            settingsGroup(interfaceHeading, [row(title: languageTitle, control: languagePopup, stacked: true), row(title: startupTitle, control: startupSwitch), startupHint, loginItemsButton, row(title: updateTitle, control: updateSwitch), updateActions])
        ]
        categoryHost.orientation = .vertical; categoryHost.alignment = .leading; categoryHost.spacing = 16
        stack.addArrangedSubview(categoryHost)
        categoryHost.widthAnchor.constraint(equalTo: stack.widthAnchor).isActive = true
        for (pane, identifier) in zip(categoryPanes, ["appearanceSettingsGroup", "chatSettingsGroup", "generalSettingsGroup"]) {
            pane.setAccessibilityIdentifier(identifier)
        }
        let buttons = NSStackView(views: [hideButton, resetButton, demoButton, NSView(), doneButton])
        buttons.orientation = .horizontal; buttons.alignment = .centerY; buttons.spacing = 10
        stack.addArrangedSubview(buttons)
        buttons.widthAnchor.constraint(equalTo: stack.widthAnchor).isActive = true
        configureActions()
        updateSettingsLayout()
    }

    private func settingsGroup(_ heading: NSTextField, _ controls: [NSView]) -> NSStackView {
        let pane = NSStackView(views: [heading] + controls)
        pane.orientation = .vertical; pane.alignment = .leading; pane.spacing = 12
        pane.edgeInsets = NSEdgeInsets(top: 20, left: 16, bottom: 20, right: 16)
        pane.wantsLayer = true; pane.layer?.backgroundColor = NSColor.white.cgColor
        pane.layer?.cornerRadius = 12; pane.layer?.borderWidth = 1
        pane.layer?.borderColor = NSColor(calibratedWhite: 0.88, alpha: 1).cgColor
        for view in [heading] + controls {
            view.widthAnchor.constraint(equalTo: pane.widthAnchor, constant: -32).isActive = true
        }
        return pane
    }

    private func updateSettingsLayout() {
        guard !categoryPanes.isEmpty else { return }
        let width = root.bounds.width > 0 ? root.bounds.width : 1100
        let columns = width >= 1000 ? 3 : (width >= 680 ? 2 : 1)
        guard columns != columnCount else { return }
        columnCount = columns
        for pane in categoryPanes { pane.removeFromSuperview() }
        for row in categoryHost.arrangedSubviews { row.removeFromSuperview() }
        for start in stride(from: 0, to: categoryPanes.count, by: columns) {
            let panes = Array(categoryPanes[start..<min(start + columns, categoryPanes.count)])
            let row = NSStackView(views: panes)
            row.orientation = .horizontal; row.alignment = .top
            row.distribution = .fillEqually; row.spacing = 16
            // Keep the last card the same width when the overview wraps to two columns.
            for _ in panes.count..<columns { row.addArrangedSubview(NSView()) }
            categoryHost.addArrangedSubview(row)
            row.widthAnchor.constraint(equalTo: categoryHost.widthAnchor).isActive = true
        }
    }

    private func configureActions() {
        lowerSignButton.bezelStyle = .regularSquare
        lowerSignButton.bezelColor = NSColor(calibratedRed: 0.18, green: 0.43, blue: 0.54, alpha: 1)
        lowerSignButton.contentTintColor = .white
        lowerSignButton.font = .systemFont(ofSize: 18, weight: .semibold)
        lowerSignButton.image = NSImage(systemSymbolName: "square.and.arrow.down", accessibilityDescription: nil)?
            .withSymbolConfiguration(.init(pointSize: 36, weight: .medium))
        lowerSignButton.imagePosition = .imageLeading
        lowerSignButton.imageScaling = .scaleNone
        lowerSignButton.target = self
        lowerSignButton.action = #selector(lowerSign)
        lowerSignButton.setAccessibilityIdentifier("lowerSignButton")
        startupSwitch.target = self
        idleHideSwitch.target = self
        idleHideSwitch.action = #selector(idleHideChanged)
        idleHideSwitch.setAccessibilityIdentifier("hideWhenIdleSwitch")

        startupSwitch.action = #selector(startupChanged)
        startupSwitch.setAccessibilityIdentifier("launchAtLoginSwitch")
        loginItemsButton.bezelStyle = .rounded
        loginItemsButton.target = self
        loginItemsButton.action = #selector(openLoginItems)
        followSwitch.target = self
        followSwitch.action = #selector(followChanged)
        providerPopup.target = self
        providerPopup.action = #selector(providerChanged)
        chatPopup.target = self
        chatPopup.action = #selector(chatChanged)
        bubbleSwitch.target = self
        bubbleSwitch.action = #selector(bubbleChanged)
        cardsSwitch.target = self
        cardsSwitch.action = #selector(cardsChanged)
        questionSwitch.target = self
        questionSwitch.action = #selector(questionChanged)

        scaleSlider.minValue = ScaleSliderView.range.lowerBound
        scaleSlider.maxValue = ScaleSliderView.range.upperBound
        scaleSlider.isContinuous = true
        scaleSlider.target = self
        scaleSlider.action = #selector(scaleChanged)

        skinPopup.target = self
        skinPopup.action = #selector(skinChanged)
        skinPopup.setAccessibilityIdentifier("skinPopup")
        skinPopup.menu?.delegate = self
        languagePopup.target = self
        languagePopup.action = #selector(languageChanged)
        hideButton.bezelStyle = .rounded
        // 空格键：设置窗口在最前面时按一下就收起／显示。
        hideButton.keyEquivalent = " "
        hideButton.target = self
        hideButton.action = #selector(toggleHidden)
        hideButton.toolTip = tr("Shortcut: Space", "快捷键：空格")
        resetButton.bezelStyle = .rounded
        resetButton.target = self
        resetButton.action = #selector(resetPosition)
        demoButton.bezelStyle = .rounded
        demoButton.target = self
        demoButton.action = #selector(toggleDemo)
        updateSwitch.target = self
        updateSwitch.action = #selector(updatePreferenceChanged)
        updateSwitch.setAccessibilityIdentifier("automaticUpdatesSwitch")
        updateButton.bezelStyle = .rounded
        updateButton.target = self
        updateButton.action = #selector(checkForUpdates)
        updateButton.setAccessibilityIdentifier("checkForUpdatesButton")
        quitButton.bezelStyle = .rounded
        quitButton.target = self
        quitButton.action = #selector(quitApp)
        quitButton.setAccessibilityIdentifier("quitYukioButton")
        doneButton.bezelStyle = .rounded
        doneButton.keyEquivalent = "\r"
        doneButton.target = self
        doneButton.action = #selector(closePanel)
        doneButton.setAccessibilityIdentifier("settingsDoneButton")

        // 设置窗口会定时刷新状态；菜单展开时将刷新合并到关闭之后，避免菜单跟踪死锁。
        providerPopup.menu?.delegate = self
        chatPopup.menu?.delegate = self
        languagePopup.menu?.delegate = self
    }

    func menuWillOpen(_ menu: NSMenu) {
        trackingPopupMenu = true
    }

    func menuDidClose(_ menu: NSMenu) {
        trackingPopupMenu = false
        guard let snapshot = pendingSnapshot else { return }
        pendingSnapshot = nil
        apply(snapshot)
    }

    private func refreshLabels(language: UILanguage) {
        labelLanguage = language
        window?.title = tr("Yukio Settings", "雪绪设置")
        brandLabel.stringValue = tr("YUKIO SETTINGS", "雪绪设置")
        followingHeading.stringValue = tr("Chats & notices", "聊天与提醒")
        displayHeading.stringValue = tr("Appearance", "外观与显示")
        interfaceHeading.stringValue = tr("General", "通用设置")
        startupTitle.stringValue = tr("Launch at login", "登录时自动启动")
        startupSwitch.setAccessibilityLabel(startupTitle.stringValue)
        startupSwitch.toolTip = tr("Open Yukio automatically when you log in to your Mac.", "登录 Mac 后自动打开雪绪。")
        startupHint.stringValue = tr("Allow Yukio in macOS Login Items to finish enabling automatic launch.", "请在 macOS 的登录项中允许雪绪，自动启动才会生效。")
        loginItemsButton.title = tr("Open Login Items…", "打开系统登录项…")
        followTitle.stringValue = tr("Follow activity", "跟随助手活动")
        providerTitle.stringValue = tr("Assistant", "跟随的助手")
        chatTitle.stringValue = tr("Pet follows chat", "桌宠跟随的聊天")
        bubbleTitle.stringValue = tr("Task bubble", "任务气泡")
        idleHideTitle.stringValue = tr("Hide when idle", "待机时隐身")
        idleHideSwitch.setAccessibilityLabel(idleHideTitle.stringValue)
        idleHideSwitch.toolTip = tr("Hide while idle and appear when working or showing a notice.", "待机时隐身，工作或有提醒时自动现形。")
        cardsTitle.stringValue = tr("Other chats", "其他聊天提醒")
        questionTitle.stringValue = tr("Answer here", "在这儿回答问题")
        skinTitle.stringValue = tr("Skin", "皮肤")
        skinPopup.setAccessibilityLabel(skinTitle.stringValue)
        scaleTitle.stringValue = tr("Size", "大小")
        languageTitle.stringValue = tr("Language", "语言")
        resetButton.title = tr("Reset position", "复位位置")
        updateTitle.stringValue = tr("Automatically check for updates", "自动检查新版本")
        updateSwitch.toolTip = tr("Check for new versions and remind me. Download and install only after I choose Install Update.", "自动检查并提醒；点击“安装更新”后才会下载和安装。")
        let version = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "dev"
        updateButton.title = tr("Check for updates…", "检查更新…") + " (" + version + ")"
        quitButton.title = tr("Quit Yukio", "退出雪绪")
        doneButton.title = tr("Done", "完成")
        lowerSignButton.title = tr("Lower sign", "取消举牌")
        lowerSignButton.toolTip = tr("Lower the current completion sign without opening the chat.", "放下当前完成牌，不打开聊天。")
        lowerSignButton.setAccessibilityLabel(lowerSignButton.title)
        browserChatButton.title = BrowserOpenChat.hasAccessibilityAccess
            ? tr("Chat recognition: permission granted…", "聊天识别：已获权限…")
            : tr("Auto-lower needs Accessibility…", "自动放牌需要辅助功能权限…")
        browserChatButton.toolTip = tr("Recognize visible chats in supported desktop apps, web pages and extensions. Only a reliably identified chat lowers its own completion sign; permission alone does not guarantee recognition. You can still lower a sign manually.",
                                      "识别受支持桌面 App、网页和扩展中可见的聊天。只有可靠识别到对应聊天才放下它的完成牌；有权限不代表已经识别成功。仍可手动放牌。")


        for heading in [followingHeading, displayHeading, interfaceHeading] {
            heading.font = .systemFont(ofSize: 15, weight: .semibold)
            heading.textColor = NSColor(calibratedRed: 0.18, green: 0.40, blue: 0.30, alpha: 1)
        }
    }

    private func row(title: NSTextField, control: NSView, stacked: Bool = false) -> NSView {
        title.font = .systemFont(ofSize: 13)
        title.textColor = .labelColor
        title.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        title.maximumNumberOfLines = 2
        title.cell?.wraps = true
        let row = NSStackView(views: stacked ? [title, control] : [title, NSView(), control])
        row.orientation = stacked ? .vertical : .horizontal
        row.alignment = stacked ? .leading : .centerY
        row.spacing = stacked ? 6 : 8
        row.translatesAutoresizingMaskIntoConstraints = false
        row.heightAnchor.constraint(equalToConstant: stacked ? 56 : 36).isActive = true
        if stacked {
            title.widthAnchor.constraint(equalTo: row.widthAnchor).isActive = true
            control.widthAnchor.constraint(equalTo: row.widthAnchor).isActive = true
            control.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        }
        return row
    }

    private func position(near anchor: NSRect) {
        guard let window else { return }
        let screen = NSScreen.screens.first(where: { $0.visibleFrame.intersects(anchor) }) ?? NSScreen.main
        guard let visible = screen?.visibleFrame else { return }
        let size = window.frame.size
        let right = anchor.maxX + 12
        let left = anchor.minX - size.width - 12
        let x = left >= visible.minX ? left : min(right, visible.maxX - size.width)
        let y = min(max(anchor.midY - size.height / 2, visible.minY + 12), visible.maxY - size.height - 12)
        window.setFrameOrigin(NSPoint(x: x, y: y))
    }

    @objc private func quitApp() { onChange?(.quit) }
    @objc private func checkForUpdates() { onChange?(.checkForUpdates) }
    @objc private func updatePreferenceChanged() {
        guard !updating else { return }
        onChange?(.automaticUpdates(updateSwitch.state == .on))
    }

    @objc private func startupChanged() {
        guard !updating else { return }
        onChange?(.launchAtLogin(startupSwitch.state == .on))
    }

    @objc private func openLoginItems() { onChange?(.openLoginItems) }

    func showStartupError(_ error: Error) {
        guard let window = root.window ?? window else { return }
        let alert = NSAlert()
        alert.alertStyle = .warning
        alert.messageText = tr("Couldn’t update automatic launch", "未能更改自动启动设置")
        alert.informativeText = error.localizedDescription
        alert.addButton(withTitle: tr("OK", "好"))
        alert.beginSheetModal(for: window)
    }

    @objc private func idleHideChanged() {
        guard !updating else { return }
        onChange?(.hideWhenIdle(idleHideSwitch.state == .on))
    }

    @objc private func followChanged() {
        guard !updating else { return }
        onChange?(.following(followSwitch.state == .on))
    }

    @objc private func providerChanged() {
        guard !updating else { return }
        let provider = AgentProvider(code: providerPopup.selectedItem?.representedObject as? String)
        // 先让 AppKit 结束下拉菜单跟踪，再扫描新来源并刷新设置内容。
        pendingSnapshot = nil
        DispatchQueue.main.async { [weak self] in self?.onChange?(.provider(provider)) }
    }

    @objc private func chatChanged() {
        guard !updating else { return }
        let value = chatPopup.selectedItem?.representedObject as? String
        onChange?(.chat(value?.isEmpty == false ? value : nil))
    }

    @objc private func bubbleChanged() {
        guard !updating else { return }
        onChange?(.showBubble(bubbleSwitch.state == .on))
    }

    @objc private func cardsChanged() {
        guard !updating else { return }
        onChange?(.showCards(cardsSwitch.state == .on))
    }

    @objc private func questionChanged() {
        guard !updating else { return }
        onChange?(.showQuestionCard(questionSwitch.state == .on))
    }

    @objc private func scaleChanged() {
        guard !updating else { return }
        let value = ScaleSliderView.snap(scaleSlider.doubleValue)
        scaleSlider.doubleValue = value
        scaleReadout.stringValue = "\(Int((value * 100).rounded()))%"
        onChange?(.scale(CGFloat(value)))
    }

    @objc private func skinChanged() {
        guard !updating, let value = skinPopup.selectedItem?.representedObject as? String,
              let picked = PetSkin(rawValue: value) else { return }
        onChange?(.skin(picked))
    }

    @objc private func languageChanged() {
        guard !updating else { return }
        onChange?(.language(UILanguage(code: languagePopup.selectedItem?.representedObject as? String)))
    }

    @objc private func toggleHidden() { onChange?(.toggleHidden) }
    @objc private func resetPosition() { onChange?(.resetPosition) }
    @objc private func toggleDemo() { onChange?(.toggleDemo) }
    @objc private func lowerSign() { onChange?(.lowerSign) }
    @objc private func browserChatPermission() { onChange?(.browserChatPermission) }
    @objc private func closePanel() { if let onEmbeddedDone { onEmbeddedDone() } else { close() } }
}

/// `--settings-snapshot out.png`：离屏画出真实设置面板内容，供设计核查。
func runSettingsSnapshot(path: String) -> Never {
    _ = NSApplication.shared
    L10n.language = .chinese
    let controller = SettingsPanelController()
    let chats = [
        SessionSummary(id: "demo-running", title: "设置界面优化", state: .default_work,
                       live: true, raisedSign: false, quietMs: 0, focused: true, pinned: false),
        SessionSummary(id: "demo-ready", title: "动作素材检查", state: .task_complete,
                       live: false, wantsYou: true, raisedSign: true, quietMs: 20_000,
                       focused: false, pinned: false),
    ]
    controller.apply(SettingsSnapshot(status: "正在跟随 GPT（Codex） · 正在工作",
                                      following: true,
                                      hidden: false,
                                      provider: .gpt,
                                      chats: chats,
                                      showBubble: true,
                                      showCards: true,
                                      showQuestionCard: true,
                                      scale: 1.0,
                                      language: .chinese,
                                      demoPlaying: false))
    guard let view = controller.window?.contentView else { exit(1) }
    view.layoutSubtreeIfNeeded()
    guard let rep = view.bitmapImageRepForCachingDisplay(in: view.bounds) else { exit(1) }
    view.cacheDisplay(in: view.bounds, to: rep)
    guard let data = rep.representation(using: .png, properties: [:]) else { exit(1) }
    do {
        try data.write(to: URL(fileURLWithPath: path), options: .atomic)
        print(path)
        exit(0)
    } catch {
        fputs("无法写入设置预览：\(error)\n", stderr)
        exit(1)
    }
}
