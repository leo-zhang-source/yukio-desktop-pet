import AppKit
import YukioCore

/// 立在她身边的那张问题卡的窗口。
///
/// 和气泡、卡叠一样是跟着她走的透明子窗口，但这一张要收键盘输入（自己写一句回答），
/// 所以它能成为 key 窗口——不过只有你点输入框时才取键盘焦点，不激活目标聊天，
/// 问题立起来的那一刻不抢你正在敲的东西。
final class QuestionPanel: NSPanel {
    let cardView = QuestionCardView(frame: NSRect(x: 0, y: 0, width: QuestionCardLayout.width, height: 40))
    private var diagnosticTimer: Timer?

    init() {
        super.init(contentRect: NSRect(x: 0, y: 0, width: QuestionCardLayout.width, height: 40),
                   styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
        isOpaque = false
        backgroundColor = .clear
        hasShadow = false
        level = .floating
        collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .ignoresCycle]
        hidesOnDeactivate = false
        isReleasedWhenClosed = false
        isMovable = false
        alphaValue = 0
        contentView = cardView
        let args = ProcessInfo.processInfo.arguments
        if let index = args.firstIndex(of: "--input-diagnostics"), args.indices.contains(index + 1) {
            cardView.inputDiagnostics = QuestionInputDiagnostics(url: URL(fileURLWithPath: args[index + 1]))
            diagnosticTimer = Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { [weak self] _ in
                self?.cardView.recordInputState("state")
            }
        }
    }

    override func performKeyEquivalent(with event: NSEvent) -> Bool {
        // Accessory panels may exist before the assistant window installs an Edit menu.
        // Route standard shortcuts to this field editor, never to another application's editor.
        if event.modifierFlags.intersection([.command, .control, .option, .shift]) == .command,
           let editor = firstResponder as? NSTextView, editor.isEditable {
            switch event.charactersIgnoringModifiers?.lowercased() {
            case "v": editor.paste(nil); return true
            case "c": editor.copy(nil); return true
            case "x": editor.cut(nil); return true
            case "a": editor.selectAll(nil); return true
            case "z": editor.undoManager?.undo(); return true
            default: break
            }
        }
        return super.performKeyEquivalent(with: event)
    }

    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { false }
    deinit { diagnosticTimer?.invalidate() }
}

/// 问题卡的正文：选项和提示是画出来的，只有输入框是真正的 NSTextField
/// （中文输入法、选词、光标都交给系统，不自己做一套）。
final class QuestionCardView: NSView, NSTextFieldDelegate {
    var inputDiagnostics: QuestionInputDiagnostics?
    var diagnosticRequestID = "none"
    /// 这张卡的排版（属性不叫 layout：NSView 自己有个同名方法）。
    var card: QuestionCardLayout? {
        didSet {
            needsDisplay = true
            placeField()
        }
    }

    /// 点了第几个选项。
    var onOption: ((Int) -> Void)?
    /// 送出输入框里的话。
    var onSend: ((String) -> Void)?
    /// 点了“打开聊天”。
    var onOpenChat: (() -> Void)?
    /// 点了 ✕：这一轮先不在这儿答。
    var onClose: (() -> Void)?
    /// 点在卡片上（控制器用来把窗口变成 key，好让输入法能用）。
    var onActivate: (() -> Void)?

    let field = NSTextField(frame: .zero)

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        field.isBordered = false
        field.drawsBackground = false
        field.focusRingType = .none
        field.font = NSFont.systemFont(ofSize: 11.5)
        field.textColor = CardLook.ink
        field.placeholderString = tr("Type your own answer", "自己写一句…")
        field.delegate = self
        field.cell?.lineBreakMode = .byTruncatingHead
        field.isHidden = true
        addSubview(field)
    }

    required init?(coder: NSCoder) { fatalError("not used") }

    override var isOpaque: Bool { false }
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
    override var acceptsFirstResponder: Bool { true }

    override func draw(_ dirtyRect: NSRect) {
        card?.draw(in: bounds)
    }

    private func placeField() {
        defer { recordInputState("layout") }
        guard let card else {
            field.isHidden = true
            return
        }
        field.isHidden = card.isApproval
        if field.isEnabled == card.isSending {
            // AppKit can discard the active field editor when disabling a field.
            // Preserve its uncommitted draft so a failed send remains editable.
            let draft = field.currentEditor()?.string
            field.isEnabled = !card.isSending
            if let draft { field.stringValue = draft }
        }
        field.frame = card.textFieldFrame(in: bounds).insetBy(dx: 5, dy: 4)
    }

    override func setFrameSize(_ newSize: NSSize) {
        super.setFrameSize(newSize)
        placeField()
    }

    /// Keep the exact active draft; trimming belongs only to sending.
    var draftText: String {
        get { field.currentEditor()?.string ?? field.stringValue }
        set {
            // End this question's editing before replacing it with another draft.
            window?.makeFirstResponder(nil)
            field.stringValue = newValue
        }
    }

    var answerText: String {
        get { draftText.trimmingCharacters(in: .whitespacesAndNewlines) }
        set { draftText = newValue }
    }

    func focusField() {
        window?.makeFirstResponder(field)
        recordInputState("focus_requested")
    }

    override func mouseDown(with event: NSEvent) {
        recordInputState("card_mouse_down")
        // 和点雪绪一样在 mouseUp 里处理；这里只把窗口变成 key，输入法才用得上。
        if card?.hit(at: convert(event.locationInWindow, from: nil), in: bounds) == .input { onActivate?() }
    }

    override func mouseUp(with event: NSEvent) {
        let point = convert(event.locationInWindow, from: nil)
        switch card?.hit(at: point, in: bounds) {
        case .option(let i): onOption?(i)
        case .input: focusField()
        case .send: onSend?(answerText)
        case .openChat: onOpenChat?()
        case .close: onClose?()
        case nil: break
        }
    }

    /// 数字键 1–9 等于点对应的选项，Esc 等于点 ✕。输入框拿到焦点时这些键归输入框。
    override func keyDown(with event: NSEvent) {
        guard card?.isSending != true else { return }
        guard let chars = event.charactersIgnoringModifiers, let first = chars.first else {
            super.keyDown(with: event)
            return
        }
        if first == "\u{1b}" { onClose?(); return }
        if first == "\r" || first == "\u{3}" { if card?.isApproval != true { onSend?(answerText) }; return }
        if let n = first.wholeNumberValue, n >= 1, n <= (card?.options.count ?? 0) {
            onOption?(n - 1)
            return
        }
        super.keyDown(with: event)
    }

    // MARK: 输入框

    func control(_ control: NSControl, textView: NSTextView, doCommandBy selector: Selector) -> Bool {
        guard card?.isSending != true else { return true }
        switch selector {
        case #selector(NSResponder.insertNewline(_:)):
            if textView.hasMarkedText() { return false }
            recordInputState("send_requested")
            onSend?(answerText)
            return true
        case #selector(NSResponder.cancelOperation(_:)):
            // The input method owns Escape while composing. A normal Escape
            // hides the card; the controller saves this question's exact draft.
            if textView.hasMarkedText() { recordInputState("ime_cancel"); return false }
            recordInputState("dismiss_requested")
            onClose?()
            return true
        default:
            return false
        }
    }

    func controlTextDidBeginEditing(_ obj: Notification) { recordInputState("editing_began") }
    func controlTextDidEndEditing(_ obj: Notification) { recordInputState("editing_ended") }
    func controlTextDidChange(_ obj: Notification) { recordInputState("text_changed") }

    func recordInputState(_ event: String) {
        guard let inputDiagnostics else { return }
        let editor = field.currentEditor() as? NSTextView
        inputDiagnostics.record([
            "event": event, "request": diagnosticRequestID,
            "key_window": window?.isKeyWindow ?? false,
            "editor_focused": editor != nil && window?.firstResponder === editor,
            "enabled": field.isEnabled, "editable": field.isEditable,
            "visible": window?.isVisible ?? false, "field_hidden": field.isHidden,
            "ignores_mouse": window?.ignoresMouseEvents ?? true,
            "sending": card?.isSending ?? false, "marked_text": editor?.hasMarkedText() ?? false,
            "draft_length": draftText.count
        ])
    }
}

/// Explicit opt-in, private and bounded. No answer text, chat IDs, paths, or keys.
final class QuestionInputDiagnostics {
    private let handle: FileHandle
    private var written = 0
    private var previous: Data?
    init?(url: URL) {
        // Never overwrite or append to an existing file (including symlinks).
        let fd = open(url.path, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, S_IRUSR | S_IWUSR)
        guard fd >= 0 else { return nil }
        handle = FileHandle(fileDescriptor: fd, closeOnDealloc: true)
    }
    func record(_ state: [String: Any]) {
        guard written < 1_048_576,
              let signature = try? JSONSerialization.data(withJSONObject: state, options: [.sortedKeys]),
              signature != previous else { return }
        previous = signature
        var row = state
        row["time"] = Date().timeIntervalSince1970
        guard var data = try? JSONSerialization.data(withJSONObject: row, options: [.sortedKeys]),
              written + data.count + 1 <= 1_048_576 else { return }
        data.append(10)
        do { try handle.write(contentsOf: data); written += data.count }
        catch { written = 1_048_576 }
    }
}
