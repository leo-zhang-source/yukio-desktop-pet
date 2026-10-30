import AppKit
import YukioCore

final class ProbePet: NSPanel { override var canBecomeKey: Bool { false } }
final class InputProbe: NSObject, NSApplicationDelegate {
    let output: URL
    let panel = QuestionPanel()
    let control = NSWindow(contentRect: NSRect(x: 120, y: 160, width: 670, height: 200),
                           styleMask: [.titled, .closable], backing: .buffered, defer: false)
    let host = ProbePet(contentRect: NSRect(x: 450, y: 420, width: 120, height: 120),
                        styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
    let status = NSTextField(labelWithString: "")
    var question = 1, attempts = 0, matches = 0
    var notice: String?, sending = false
    var timer: Timer?
    var lastState = ""
    let expected = "Yukio 你好123"
    init(output: URL) { self.output=output; super.init() }

    func applicationDidFinishLaunching(_ notification: Notification) {
        L10n.language = .chinese
        let menu=NSMenu()
        let appItem=NSMenuItem();menu.addItem(appItem)
        let appMenu=NSMenu();appItem.submenu=appMenu
        for (title,action,key) in [("下一题",#selector(nextQuestion),"n"),("刷新当前题",#selector(refresh),"r"),
                                   ("发送中再失败",#selector(failSending),"f"),("隐藏再显示",#selector(hideAndShow),"h"),
                                   ("问题卡",#selector(showQuestion),"2"),("结束并保存",#selector(finish),"q")] {
            let item=NSMenuItem(title:title,action:action,keyEquivalent:key);item.target=self;appMenu.addItem(item)
        }
        NSApp.mainMenu=menu
        control.title = "Yukio 输入诊断 · 只用人工测试文字"
        control.isReleasedWhenClosed = false
        let explanation = NSTextField(wrappingLabelWithString: "在旁边的问题卡输入 Yukio 你好123，然后按回车。不会连接或发送到真实聊天。日志只记录焦点、长度与是否匹配。")
        var buttons: [NSButton] = []
        for (title, action) in [("下一题", #selector(nextQuestion)), ("刷新当前题", #selector(refresh)),
                                ("发送中再失败", #selector(failSending)), ("隐藏再显示", #selector(hideAndShow)),
                                ("结束并保存", #selector(finish))] {
            let b=NSButton(title: title, target: self, action: action);b.bezelStyle = .rounded;buttons.append(b)
        }
        let row=NSStackView(views: buttons);row.orientation = .horizontal;row.spacing=8
        let stack=NSStackView(views: [explanation,row,status]);stack.orientation = .vertical;stack.spacing=20;stack.alignment = .leading
        control.contentView=stack
        host.title="人工测试锚点";host.level = .floating;host.isReleasedWhenClosed=false
        let anchor=NSTextField(wrappingLabelWithString: "问题卡测试\n无真实聊天")
        anchor.frame=NSRect(x: 10,y: 20,width: 100,height: 70);host.contentView?.addSubview(anchor)
        panel.title="人工输入问题";panel.alphaValue=1;panel.ignoresMouseEvents=false
        panel.cardView.field.setAccessibilityIdentifier("remediationQuestionInput")
        panel.cardView.field.setAccessibilityLabel("人工问题回答")
        panel.cardView.onActivate = { [weak self] in
            guard let self else { return }
            self.panel.makeKeyAndOrderFront(nil)
            self.panel.makeFirstResponder(self.panel.cardView)
            self.record("activate")
        }
        panel.cardView.onSend = { [weak self] text in self?.received(text) }
        panel.cardView.onClose = { [weak self] in self?.panel.orderOut(nil);self?.record("dismiss") }
        host.orderFrontRegardless();host.addChildWindow(panel, ordered: .above)
        draw()
        control.makeKeyAndOrderFront(nil);NSApp.activate(ignoringOtherApps: true)
        showQuestion()
        record("started")
        timer=Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { [weak self] _ in self?.record("state") }
    }
    func draw() {
        let card=QuestionCardLayout(PetQuestion(text: "测试第 \(question) 题：请输入指定文字", options: []),
                                    canOpenChat: false, sentNotice: notice, isSending: sending)
        panel.cardView.card=card
        panel.setFrame(NSRect(x: host.frame.maxX+12,y: host.frame.minY,width: card.size.width,height: card.size.height),display: true)
        panel.cardView.frame=NSRect(origin: .zero,size: card.size)
        panel.orderFrontRegardless()
        status.stringValue="第 \(question) 题；收到 \(attempts) 次测试答案，其中 \(matches) 次与指定文字一致。"
    }
    @objc func nextQuestion() {
        question += 1;notice=nil;sending=false;panel.cardView.answerText="";draw();record("next_question")
    }
    @objc func refresh() { draw();record("refresh") }
    @objc func showQuestion() { panel.makeKeyAndOrderFront(nil);record("explicit_show_question") }
    @objc func failSending() {
        sending=true;notice="模拟发送中";draw();record("sending")
        DispatchQueue.main.asyncAfter(deadline: .now()+1) { [weak self] in
            guard let self else { return };self.sending=false;self.notice="模拟失败，可继续编辑";self.draw();self.record("send_failed")
        }
    }
    @objc func hideAndShow() {
        panel.orderOut(nil);record("hidden")
        DispatchQueue.main.asyncAfter(deadline: .now()+0.5) { [weak self] in self?.draw();self?.record("shown_without_activation") }
    }
    func received(_ text: String) {
        attempts += 1
        if text==expected { matches += 1 }
        record("answer", extra: ["matches_fixture":text==expected,"received_length":text.count])
        notice=text==expected ? "测试文字一致，未发送聊天" : "测试文字不一致，未发送聊天";draw()
    }
    func record(_ event: String, extra: [String: Any] = [:]) {
        let editor=panel.cardView.field.currentEditor() as? NSTextView
        var row: [String: Any] = ["event":event,"question":question,"key_is_question":panel.isKeyWindow,
            "first_responder_is_editor":editor != nil && panel.firstResponder === editor,
            "editable":panel.cardView.field.isEditable,"enabled":panel.cardView.field.isEnabled,
            "visible":panel.isVisible,"sending":sending,"marked_text":editor?.hasMarkedText() ?? false,
            "text_length":(editor?.string ?? panel.cardView.field.stringValue).count]
        row.merge(extra) { _,new in new }
        guard let encoded=try? JSONSerialization.data(withJSONObject: row,options: [.sortedKeys]),
              let signature=String(data: encoded,encoding: .utf8) else { return }
        if event=="state", signature==lastState { return };lastState=signature
        row["time"]=Date().timeIntervalSince1970
        guard var data=try? JSONSerialization.data(withJSONObject: row,options: [.sortedKeys]) else { return };data.append(10)
        let file=output.appendingPathComponent("events.jsonl")
        if !FileManager.default.fileExists(atPath: file.path) { FileManager.default.createFile(atPath: file.path,contents: nil,attributes: [.posixPermissions:0o600]) }
        if let handle=try? FileHandle(forWritingTo: file) { try? handle.seekToEnd();try? handle.write(contentsOf: data);try? handle.close() }
    }
    @objc func finish() {
        record("finished",extra: ["attempts":attempts,"matching_answers":matches]);timer?.invalidate();panel.close();host.close();control.close();NSApp.terminate(nil)
    }
}

guard CommandLine.arguments.count==2 else { exit(2) }
let out=URL(fileURLWithPath: CommandLine.arguments[1])
guard !FileManager.default.fileExists(atPath: out.path) else { exit(2) }
try FileManager.default.createDirectory(at: out, withIntermediateDirectories: true, attributes: [.posixPermissions:0o700])
let app=NSApplication.shared
app.setActivationPolicy(.accessory)
let probe=InputProbe(output: out);app.delegate=probe
withExtendedLifetime(probe) { app.run() }
