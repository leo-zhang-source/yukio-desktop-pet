import AppKit
import WebKit
import YukioCore

protocol WorkbenchStarting: AnyObject {
    func start(_ completion: @escaping (Result<URL, Error>) -> Void)
    func stop()
}

/// The bundled launcher checks the build and data scope before reusing a service.
/// A service owned by another window is never stopped by this controller.
final class WorkbenchRuntime: WorkbenchStarting {
    enum Failure: Error { case missing, unavailable }
    private var process: Process?
    private var output: Pipe?
    private var readyURL: URL?
    private var generation = UUID()
    private var callbacks: [(Result<URL, Error>) -> Void] = []
    private let resources: URL?
    init(resources: URL? = Bundle.main.resourceURL) { self.resources = resources }

    func start(_ completion: @escaping (Result<URL, Error>) -> Void) {
        if let readyURL, process?.isRunning == true { completion(.success(readyURL)); return }
        if process?.isRunning == true { callbacks.append(completion); return }
        guard let resources else { completion(.failure(Failure.missing)); return }
        let executable = resources.appendingPathComponent("activity-workbench/runtime/YukioRuntime/YukioRuntime")
        guard FileManager.default.isExecutableFile(atPath: executable.path) else {
            completion(.failure(Failure.missing)); return
        }
        callbacks = [completion]
        let finish: (Result<URL, Error>) -> Void = { [weak self] result in
            guard let self else { return }
            let waiting = self.callbacks; self.callbacks.removeAll()
            waiting.forEach { $0(result) }
        }
        let token = UUID(); generation = token
        let worker = Process(), pipe = Pipe()
        worker.executableURL = executable
        worker.arguments = ["--collect", "--no-browser"]
        worker.standardOutput = pipe; worker.standardError = pipe
        var pending = "", delivered = false
        let accept: (String) -> Void = { [weak self] text in
            guard let self, self.generation == token else { return }
            pending = String((pending + text).suffix(8192))
            if !delivered, pending.contains("http://127.0.0.1:8767/") {
                delivered = true
                let url = URL(string: "http://127.0.0.1:8767/")!
                self.readyURL = url
                finish(.success(url))
            }
        }
        pipe.fileHandleForReading.readabilityHandler = { handle in
            let bytes = handle.availableData
            if bytes.isEmpty {
                handle.readabilityHandler = nil
                DispatchQueue.main.async { [weak self] in
                    guard let self, self.generation == token, !delivered else { return }
                    delivered = true; finish(.failure(Failure.unavailable))
                }
                return
            }
            let text = String(decoding: bytes, as: UTF8.self)
            DispatchQueue.main.async { accept(text) }
        }
        worker.terminationHandler = { [weak self] _ in
            DispatchQueue.main.async {
                guard let self, self.generation == token else { return }
                // When every recorder was already running the launcher exits cleanly.
                // The pipe's EOF handler reports failures after all readiness output
                // has been consumed, even when a reused launcher exits immediately.
                self.readyURL = nil
            }
        }
        do { try worker.run(); process = worker; output = pipe }
        catch { pipe.fileHandleForReading.readabilityHandler = nil; finish(.failure(error)) }
    }

    func stop() {
        generation = UUID(); readyURL = nil; callbacks.removeAll()
        output?.fileHandleForReading.readabilityHandler = nil
        if let process, process.isRunning { process.terminate() }
        process = nil; output = nil
    }
    deinit { stop() }
}

/// The former settings entry now hosts the workbench and the existing native settings.
/// The native settings callback stays unchanged; preferences never pass through the page.
final class WorkbenchPanelController: NSWindowController, NSWindowDelegate, WKNavigationDelegate {
    var onChange: ((SettingsChange) -> Void)?
    private let runtime: WorkbenchStarting
    let settings = SettingsPanelController()
    private let outsideClickMonitor = SettingsOutsideClickMonitor()
    private let body = NSView()
    private let workButton = NSButton(title: "活动工作台", target: nil, action: nil)
    private let settingsButton = NSButton(title: "设置", target: nil, action: nil)
    private let message = NSTextField(wrappingLabelWithString: "正在打开工作台…")
    private let retryButton = NSButton(title: "重新连接", target: nil, action: nil)
    private let settingsScroll = NSScrollView()
    private(set) var webView: WKWebView?
    private(set) var showingSettings = false
    private var selectionURL: URL?
    private var opening = UUID()

    init(runtime: WorkbenchStarting = WorkbenchRuntime()) {
        self.runtime = runtime
        let panel = NSPanel(contentRect: NSRect(x: 0, y: 0, width: 1100, height: 760),
                            styleMask: [.titled, .closable, .resizable, .nonactivatingPanel],
                            backing: .buffered, defer: false)
        panel.title = "Yukio · 活动工作台"
        panel.level = .floating
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.hidesOnDeactivate = false; panel.isReleasedWhenClosed = false
        panel.minSize = NSSize(width: 760, height: 520)
        panel.appearance = NSAppearance(named: .aqua)
        super.init(window: panel)
        panel.delegate = self
        settings.onChange = { [weak self] in self?.onChange?($0) }
        settings.onEmbeddedDone = { [weak self] in self?.showWork() }
        buildUI()
    }
    required init?(coder: NSCoder) { fatalError("not used") }

    private func buildUI() {
        guard let root = window?.contentView else { return }
        let heading = NSTextField(labelWithString: "YUKIO")
        heading.font = .systemFont(ofSize: 18, weight: .semibold)
        for button in [workButton, settingsButton] {
            button.bezelStyle = .rounded; button.font = .systemFont(ofSize: 15, weight: .semibold)
            button.setButtonType(.toggle); button.target = self
            button.heightAnchor.constraint(equalToConstant: 36).isActive = true
        }
        workButton.action = #selector(showWork); workButton.setAccessibilityIdentifier("workbenchTab")
        settingsButton.action = #selector(showSettings); settingsButton.setAccessibilityIdentifier("petSettingsTab")
        settingsButton.image = NSImage(systemSymbolName: "gearshape.fill", accessibilityDescription: nil)
        settingsButton.imagePosition = .imageLeading
        settingsButton.contentTintColor = .controlAccentColor
        settingsButton.widthAnchor.constraint(equalToConstant: 110).isActive = true
        settingsButton.toolTip = "雪绪的大小、显示、聊天、换装与其他设置"
        let header = NSStackView(views: [heading, workButton, NSView(), settingsButton])
        header.orientation = .horizontal; header.spacing = 18; header.alignment = .centerY
        for view in [header, body] { view.translatesAutoresizingMaskIntoConstraints = false; root.addSubview(view) }
        NSLayoutConstraint.activate([
            header.topAnchor.constraint(equalTo: root.topAnchor, constant: 10),
            header.leadingAnchor.constraint(equalTo: root.leadingAnchor, constant: 20),
            header.trailingAnchor.constraint(equalTo: root.trailingAnchor, constant: -20),
            body.topAnchor.constraint(equalTo: header.bottomAnchor, constant: 10),
            body.leadingAnchor.constraint(equalTo: root.leadingAnchor), body.trailingAnchor.constraint(equalTo: root.trailingAnchor),
            body.bottomAnchor.constraint(equalTo: root.bottomAnchor),
        ])
        let settingsView = settings.embeddedView()
        settingsScroll.documentView = settingsView
        settingsScroll.hasVerticalScroller = true; settingsScroll.drawsBackground = true
        settingsScroll.backgroundColor = NSColor(calibratedWhite: 0.965, alpha: 1)
        settingsScroll.appearance = NSAppearance(named: .aqua)
        settingsView.appearance = NSAppearance(named: .aqua)
        settingsView.translatesAutoresizingMaskIntoConstraints = false
        settingsView.widthAnchor.constraint(equalTo: settingsScroll.contentView.widthAnchor).isActive = true
        // The settings' own fixed-width rows stay readable; the scroll view handles small screens.
        message.font = .systemFont(ofSize: 16)
        retryButton.target = self; retryButton.action = #selector(retry)
        retryButton.bezelStyle = .rounded
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
    func showStartupError(_ error: Error) { settings.showStartupError(error) }

    private func fill(_ view: NSView) {
        body.subviews.forEach { $0.removeFromSuperview() }
        body.addSubview(view); view.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([view.leadingAnchor.constraint(equalTo: body.leadingAnchor), view.trailingAnchor.constraint(equalTo: body.trailingAnchor),
            view.topAnchor.constraint(equalTo: body.topAnchor), view.bottomAnchor.constraint(equalTo: body.bottomAnchor)])
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
        message.stringValue = "正在打开工作台…"
        let loading = NSStackView(views: [message, retryButton])
        loading.orientation = .vertical; loading.alignment = .centerX; loading.spacing = 18
        fill(loading)
        let token = UUID(); opening = token
        runtime.start { [weak self] result in
            guard let self, self.opening == token, self.window?.isVisible == true, !self.showingSettings else { return }
            switch result {
            case .success(let url):
                let configuration = WKWebViewConfiguration()
                configuration.websiteDataStore = .nonPersistent()
                let web = WKWebView(frame: .zero, configuration: configuration)
                web.navigationDelegate = self; self.webView = web; self.fill(web)
                web.load(URLRequest(url: self.selectionURL ?? url))
            case .failure:
                self.message.stringValue = "工作台暂时没连上。可以点“重新连接”，右上角的“设置”仍可使用。"
            }
        }
    }

    @objc private func retry() { showWork() }

    private func pausePage() {
        if let url = webView?.url, Self.isLocal(url) { selectionURL = url }
        webView?.evaluateJavaScript("window.dispatchEvent(new Event('pagehide'))", completionHandler: nil)
    }

    private func dismissContent() {
        opening = UUID(); outsideClickMonitor.stop(); pausePage()
        // Destroy timers and page-owned model work. No hidden browser remains after closing.
        if let web = webView {
            web.stopLoading(); web.loadHTMLString("", baseURL: nil); web.removeFromSuperview()
        }
        webView = nil
    }
    override func close() { dismissContent(); super.close() }
    func windowWillClose(_ notification: Notification) { dismissContent() }
    func shutdown() { dismissContent(); runtime.stop() }

    static func isLocal(_ url: URL) -> Bool {
        url.scheme == "http" && url.host == "127.0.0.1" && url.port == 8767 && url.user == nil && url.password == nil
    }
    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        let allowed = navigationAction.request.url.map { Self.isLocal($0) || $0.absoluteString == "about:blank" } ?? false
        decisionHandler(allowed ? .allow : .cancel)
    }
}
