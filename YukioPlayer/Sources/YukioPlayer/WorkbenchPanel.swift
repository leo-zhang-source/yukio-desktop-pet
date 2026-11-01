import AppKit
import WebKit
import YukioCore

protocol WorkbenchStarting: AnyObject {
    func start(_ completion: @escaping (Result<URL, Error>) -> Void)
    func stop()
}

/// The page runs under the transparent title bar, so this strip keeps the window draggable.
private final class TitlebarDragView: NSView {
    override var mouseDownCanMoveWindow: Bool { true }
    override func mouseDown(with event: NSEvent) { window?.performDrag(with: event) }
}

/// WebKit retains its message handlers strongly; this keeps the panel free to close.
private final class WorkbenchMessages: NSObject, WKScriptMessageHandler {
    weak var target: WorkbenchPanelController?
    init(target: WorkbenchPanelController) { self.target = target }
    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        target?.handle(message)
    }
}

/// The former settings entry now hosts the workbench and the existing native settings.
/// The native settings callback stays unchanged; preferences never pass through the page.
/// While the page is showing it owns the whole window; native chrome returns for settings and failures.
final class WorkbenchPanelController: NSWindowController, NSWindowDelegate, WKNavigationDelegate {
    var onChange: ((SettingsChange) -> Void)?
    private let runtime: WorkbenchStarting
    let settings = SettingsPanelController()
    private let outsideClickMonitor = SettingsOutsideClickMonitor()
    private let body = NSView()
    private let header = NSStackView()
    private let dragStrip = TitlebarDragView()
    private var bodyBelowHeader: NSLayoutConstraint?
    private var bodyAtTop: NSLayoutConstraint?
    private let workButton = NSButton(title: "活动工作台", target: nil, action: nil)
    private let settingsButton = NSButton(title: "设置", target: nil, action: nil)
    private let message = NSTextField(wrappingLabelWithString: "正在打开工作台…")
    private let retryButton = NSButton(title: "重新连接", target: nil, action: nil)
    private let diagnosticButton = NSButton(title: "复制诊断信息", target: nil, action: nil)
    private let settingsScroll = NSScrollView()
    private(set) var webView: WKWebView?
    private(set) var showingSettings = false
    private var selectionURL: URL?
    private(set) var serviceURL: URL?
    private(set) var diagnosticText = ""
    private var opening = UUID()
    private(set) var uiLanguage: String

    static func preferredLanguage(_ languages: [String], appPreference: String? = nil) -> String {
        if let appPreference { return UILanguage(code: appPreference).rawValue }
        return (languages.first ?? "en").lowercased().hasPrefix("zh") ? "zh" : "en"
    }

    private func localized(_ zh: String, _ en: String) -> String { uiLanguage == "zh" ? zh : en }

    func localizedURL(_ url: URL) -> URL {
        var parts = URLComponents(url: url, resolvingAgainstBaseURL: false)!
        var query = (parts.queryItems ?? []).filter { $0.name != "lang" }
        query.append(URLQueryItem(name: "lang", value: uiLanguage)); parts.queryItems = query
        return parts.url!
    }

    init(runtime: WorkbenchStarting = WorkbenchRuntime(), preferredLanguages: [String] = Locale.preferredLanguages) {
        self.runtime = runtime
        self.uiLanguage = Self.preferredLanguage(preferredLanguages)
        let panel = NSPanel(contentRect: NSRect(x: 0, y: 0, width: 1100, height: 760),
                            styleMask: [.titled, .closable, .resizable, .nonactivatingPanel, .fullSizeContentView],
                            backing: .buffered, defer: false)
        panel.title = uiLanguage == "zh" ? "Yukio · 活动工作台" : "Yukio · Activity workbench"
        panel.titlebarAppearsTransparent = true; panel.titleVisibility = .hidden
        panel.level = .floating
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.hidesOnDeactivate = false; panel.isReleasedWhenClosed = false
        panel.minSize = NSSize(width: 760, height: 520)
        panel.appearance = NSAppearance(named: .aqua)
        super.init(window: panel)
        settings.presentationLanguage = UILanguage(code: uiLanguage)
        workButton.title = localized("活动工作台", "Activity workbench")
        settingsButton.title = localized("设置", "Settings")
        retryButton.title = localized("重新连接", "Reconnect")
        panel.delegate = self
        settings.onChange = { [weak self] in self?.onChange?($0) }
        settings.onEmbeddedDone = { [weak self] in self?.showWork() }
        buildUI()
    }
    required init?(coder: NSCoder) { fatalError("not used") }

    private func buildUI() {
        guard let root = window?.contentView else { return }
        let heading = NSTextField(labelWithString: "Yukio")
        heading.font = .systemFont(ofSize: 13, weight: .semibold)
        for button in [workButton, settingsButton] {
            button.bezelStyle = .rounded; button.font = .systemFont(ofSize: 13, weight: .medium)
            button.setButtonType(.toggle); button.target = self
            button.controlSize = .regular
        }
        workButton.action = #selector(showWork); workButton.setAccessibilityIdentifier("workbenchTab")
        settingsButton.action = #selector(showSettings); settingsButton.setAccessibilityIdentifier("petSettingsTab")
        settingsButton.image = NSImage(systemSymbolName: "gearshape.fill", accessibilityDescription: nil)
        settingsButton.imagePosition = .imageLeading
        settingsButton.toolTip = localized("雪绪的大小、显示、聊天、换装与其他设置", "Yukio’s size, appearance, chats, outfits and other settings")
        for view in [heading, workButton, NSView(), settingsButton] { header.addArrangedSubview(view) }
        header.orientation = .horizontal; header.spacing = 12; header.alignment = .centerY
        for view in [header, body, dragStrip] { view.translatesAutoresizingMaskIntoConstraints = false; root.addSubview(view) }
        let below = body.topAnchor.constraint(equalTo: header.bottomAnchor, constant: 8)
        bodyBelowHeader = below; bodyAtTop = body.topAnchor.constraint(equalTo: root.topAnchor)
        NSLayoutConstraint.activate([
            header.topAnchor.constraint(equalTo: root.topAnchor, constant: 4),
            header.leadingAnchor.constraint(equalTo: root.leadingAnchor, constant: 84),
            header.trailingAnchor.constraint(equalTo: root.trailingAnchor, constant: -16),
            below,
            body.leadingAnchor.constraint(equalTo: root.leadingAnchor), body.trailingAnchor.constraint(equalTo: root.trailingAnchor),
            body.bottomAnchor.constraint(equalTo: root.bottomAnchor),
            dragStrip.topAnchor.constraint(equalTo: root.topAnchor), dragStrip.heightAnchor.constraint(equalToConstant: 28),
            dragStrip.leadingAnchor.constraint(equalTo: root.leadingAnchor), dragStrip.trailingAnchor.constraint(equalTo: root.trailingAnchor),
        ])
        dragStrip.isHidden = true
        settings.embed(in: settingsScroll)
        settingsScroll.appearance = NSAppearance(named: .aqua)
        message.font = .systemFont(ofSize: 16)
        retryButton.target = self; retryButton.action = #selector(retry)
        retryButton.bezelStyle = .rounded
        diagnosticButton.target = self; diagnosticButton.action = #selector(copyDiagnostics)
        diagnosticButton.bezelStyle = .rounded
        diagnosticButton.setAccessibilityIdentifier("copyWorkbenchDiagnostics")
    }

    func show(snapshot: SettingsSnapshot, near anchor: NSRect) {
        apply(snapshot)
        guard let window else { return }
        if !window.isVisible {
            let visible = (NSScreen.screens.first { $0.visibleFrame.intersects(anchor) } ?? NSScreen.main)?.visibleFrame
            if let visible {
                let width = min(window.frame.width, visible.width - 24), height = min(window.frame.height, visible.height - 24)
                let x = max(visible.minX + 12, min(anchor.minX - width - 12, visible.maxX - width - 12))
                let y = max(visible.minY + 12, min(anchor.midY - height / 2, visible.maxY - height - 12))
                window.setFrame(NSRect(x: x, y: y, width: width, height: height), display: false)
            }
        }
        showWindow(nil); window.makeKeyAndOrderFront(nil); window.orderFrontRegardless()
        outsideClickMonitor.start(window: window, isInteracting: { [weak self] in self?.settings.isTrackingPopup ?? false },
                                  dismiss: { [weak self] in self?.close() })
        showWork()
    }

    func apply(_ snapshot: SettingsSnapshot) { settings.apply(snapshot) }
    func setLanguage(_ language: UILanguage) {
        guard uiLanguage != language.rawValue else { return }
        let wasShowingSettings = showingSettings
        dismissContent()
        uiLanguage = language.rawValue
        settings.presentationLanguage = language
        window?.title = localized("Yukio · 活动工作台", "Yukio · Activity workbench")
        workButton.title = localized("活动工作台", "Activity workbench")
        settingsButton.title = localized("设置", "Settings")
        retryButton.title = localized("重新连接", "Reconnect")
        diagnosticButton.title = localized("复制诊断信息", "Copy diagnostics")
        settingsButton.toolTip = localized("雪绪的大小、显示、聊天、换装与其他设置", "Yukio’s size, appearance, chats, outfits and other settings")
        if wasShowingSettings { showSettings() }
        else if window?.isVisible == true { showWork() }
        if let window, window.isVisible {
            outsideClickMonitor.start(window: window, isInteracting: { [weak self] in self?.settings.isTrackingPopup ?? false },
                                      dismiss: { [weak self] in self?.close() })
        }
    }
    func showStartupError(_ error: Error) { settings.showStartupError(error) }

    private func fill(_ view: NSView) {
        body.subviews.forEach { $0.removeFromSuperview() }
        body.addSubview(view); view.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([view.leadingAnchor.constraint(equalTo: body.leadingAnchor), view.trailingAnchor.constraint(equalTo: body.trailingAnchor),
            view.topAnchor.constraint(equalTo: body.topAnchor), view.bottomAnchor.constraint(equalTo: body.bottomAnchor)])
        // The page draws its own navigation, including the way into settings.
        let pageOwnsWindow = webView != nil && view === webView
        header.isHidden = pageOwnsWindow; dragStrip.isHidden = !pageOwnsWindow
        if pageOwnsWindow { bodyBelowHeader?.isActive = false; bodyAtTop?.isActive = true }
        else { bodyAtTop?.isActive = false; bodyBelowHeader?.isActive = true }
    }

    fileprivate func handle(_ message: WKScriptMessage) {
        guard message.frameInfo.isMainFrame, message.body as? String == "settings",
              let url = message.frameInfo.request.url, Self.isLocal(url, port: serviceURL?.port ?? 8767) else { return }
        showSettings()
    }

    private func releasePage() {
        webView?.configuration.userContentController.removeScriptMessageHandler(forName: "yukio")
        webView?.navigationDelegate = nil; webView?.stopLoading()
    }

    @objc func showSettings() {
        opening = UUID(); showingSettings = true
        workButton.state = .off; settingsButton.state = .on
        pausePage()
        fill(settingsScroll)
    }

    @objc func showWork() {
        showingSettings = false; workButton.state = .on; settingsButton.state = .off
        if let webView {
            fill(webView)
            webView.evaluateJavaScript("window.dispatchEvent(new Event('pageshow'))", completionHandler: nil)
            return
        }
        message.stringValue = localized("正在打开工作台…", "Opening the workbench…")
        diagnosticText = ""; diagnosticButton.isHidden = true
        let loading = NSStackView(views: [message, retryButton, diagnosticButton])
        loading.orientation = .vertical; loading.alignment = .centerX; loading.spacing = 18
        fill(loading)
        let token = UUID(); opening = token
        runtime.start { [weak self] result in
            // A running service answers synchronously, before AppKit reports the window as visible.
            // Closing the panel replaces `opening`, so a late answer still cannot reach a closed page.
            guard let self, self.opening == token, !self.showingSettings else { return }
            switch result {
            case .success(let url):
                self.serviceURL = url
                let configuration = WKWebViewConfiguration()
                configuration.websiteDataStore = .nonPersistent()
                configuration.userContentController.add(WorkbenchMessages(target: self), name: "yukio")
                let web = WKWebView(frame: .zero, configuration: configuration)
                web.navigationDelegate = self; self.webView = web; self.fill(web)
                web.load(URLRequest(url: self.localizedURL(Self.restoreSelection(self.selectionURL, at: url))))
            case .failure(let error):
                let failure = error as? WorkbenchRuntime.Failure ?? .unavailable
                self.showConnectionFailure(failure.message(english: self.uiLanguage == "en"), code: failure.code)
            }
        }
    }

    @objc private func retry() {
        runtime.stop(); serviceURL = nil; showWork()
    }

    func showConnectionFailure(_ text: String, code: String) {
        releasePage(); webView = nil
        message.stringValue = text + "\n" + localized("右上角的“设置”仍可使用。", "Settings is still available at the top right.")
        let info = Bundle.main.infoDictionary ?? [:]
        diagnosticText = "Yukio workbench\nversion=\(info["CFBundleShortVersionString"] ?? "unknown") (\(info["CFBundleVersion"] ?? "unknown"))\nmacOS=\(ProcessInfo.processInfo.operatingSystemVersionString)\ncode=\(code)"
        diagnosticButton.title = localized("复制诊断信息", "Copy diagnostics")
        diagnosticButton.isHidden = false
        let content = NSStackView(views: [message, retryButton, diagnosticButton])
        content.orientation = .vertical; content.alignment = .centerX; content.spacing = 18
        fill(content)
    }

    @objc private func copyDiagnostics() {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(diagnosticText, forType: .string)
    }

    private func pausePage() {
        if let url = webView?.url, Self.isLocal(url, port: serviceURL?.port ?? 8767) { selectionURL = url }
        webView?.evaluateJavaScript("window.dispatchEvent(new Event('pagehide'))", completionHandler: nil)
    }

    private func dismissContent() {
        opening = UUID(); outsideClickMonitor.stop(); pausePage()
        // Destroy timers and page-owned model work. No hidden browser remains after closing.
        if let web = webView {
            releasePage(); web.loadHTMLString("", baseURL: nil); web.removeFromSuperview()
        }
        webView = nil
    }
    override func close() { dismissContent(); super.close() }
    func windowWillClose(_ notification: Notification) { dismissContent() }
    func shutdown() { dismissContent(); runtime.stop() }

    static func isLocal(_ url: URL, port: Int = 8767) -> Bool {
        url.scheme == "http" && url.host == "127.0.0.1" && url.port == port && url.user == nil && url.password == nil
    }

    /// Selection was captured only from our previous service. Carry its route
    /// across a new reserved port without ever navigating back to the old owner.
    static func restoreSelection(_ saved: URL?, at service: URL) -> URL {
        guard let saved, let oldPort = saved.port, isLocal(saved, port: oldPort),
              var target = URLComponents(url: service, resolvingAgainstBaseURL: false),
              let selection = URLComponents(url: saved, resolvingAgainstBaseURL: false) else { return service }
        target.percentEncodedPath = selection.percentEncodedPath
        target.percentEncodedQuery = selection.percentEncodedQuery
        return target.url ?? service
    }
    static func isSetupDocumentation(_ url: URL) -> Bool {
        ["https://developers.openai.com/codex/cli", "https://code.claude.com/docs/en/setup"].contains(url.absoluteString)
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if navigationAction.navigationType == .linkActivated,
           let url = navigationAction.request.url, Self.isSetupDocumentation(url) {
            NSWorkspace.shared.open(url)
            decisionHandler(.cancel)
            return
        }
        let allowed = navigationAction.request.url.map { Self.isLocal($0, port: serviceURL?.port ?? 8767) || $0.absoluteString == "about:blank" } ?? false
        decisionHandler(allowed ? .allow : .cancel)
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        guard webView === self.webView, (error as NSError).code != NSURLErrorCancelled else { return }
        showConnectionFailure(localized("工作台页面连接中断，请点“重新连接”。", "The workbench page disconnected. Try Reconnect."), code: "page_\((error as NSError).code)")
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        self.webView(webView, didFailProvisionalNavigation: navigation, withError: error)
    }
}
