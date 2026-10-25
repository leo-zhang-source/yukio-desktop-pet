import AppKit

final class WorkbenchDelegate: NSObject, NSApplicationDelegate {
    var worker: Process?
    var window: NSWindow!
    let message = NSTextField(wrappingLabelWithString: "正在准备本机工作台…")
    var openButton: NSButton!
    var reuse = false
    var didOpen = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        let menu = NSMenu()
        let applicationItem = NSMenuItem(); menu.addItem(applicationItem)
        let appMenu = NSMenu(); applicationItem.submenu = appMenu
        appMenu.addItem(NSMenuItem(title: "退出工作台", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q"))
        NSApp.mainMenu = menu
        window = NSWindow(contentRect: NSRect(x:0,y:0,width:590,height:290), styleMask:[.titled,.closable,.miniaturizable], backing:.buffered, defer:false)
        window.title = "Yukio 活动工作台 · 本机试用版"
        window.center()
        let view = NSView(frame:window.contentView!.bounds); window.contentView = view
        let title = NSTextField(labelWithString:"把工作过程看清楚")
        title.font = .systemFont(ofSize:25,weight:.medium); title.frame = NSRect(x:30,y:220,width:530,height:40); view.addSubview(title)
        message.frame=NSRect(x:30,y:96,width:530,height:115); message.font = .systemFont(ofSize:14);view.addSubview(message)
        openButton=NSButton(title:"打开活动工作台",target:self,action:#selector(openWorkbench));openButton.frame=NSRect(x:30,y:35,width:165,height:36);openButton.bezelStyle = .rounded;openButton.isEnabled=false;view.addSubview(openButton)
        let quit=NSButton(title:"退出",target:NSApp,action:#selector(NSApplication.terminate(_:)));quit.frame=NSRect(x:445,y:35,width:110,height:36);quit.bezelStyle = .rounded;view.addSubview(quit)
        window.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps:true)
        guard let resources=Bundle.main.resourceURL else {message.stringValue="缺少启动文件。请重新获取试用包。";return}
        let process=Process()
        let runtime=resources.appendingPathComponent("runtime/YukioRuntime/YukioRuntime")
        if FileManager.default.isExecutableFile(atPath:runtime.path) {
            process.executableURL=runtime; process.arguments=["--collect","--no-browser"]
        } else {
            process.executableURL=URL(fileURLWithPath:"/usr/bin/env")
            process.arguments=["python3","-B",resources.appendingPathComponent("workbench/launcher.py").path,"--collect","--no-browser"]
        }
        let output=Pipe();process.standardOutput=output;process.standardError=output
        output.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data=handle.availableData
            guard !data.isEmpty,let text=String(data:data,encoding:.utf8) else{return}
            DispatchQueue.main.async {
                guard let self=self else{return}
                if text.contains("已在运行") || text.contains("http://127.0.0.1:8767/") {
                    self.reuse = text.contains("已在运行")
                    self.message.stringValue="工作台已经准备好。选择聊天后，千问会按你的设置自动解释“内容、解释、原因”；页面打开期间持续跟进，关掉页面停止后续解释。\n\n说明会结合前面的进展，用普通语言讲清正在做什么、有什么用。发送范围和接收位置在页面的“说明与隐私”中查看。此试用版不会替换原来的桌宠。退出会停止由本窗口启动的服务；已有服务继续运行。"
                    self.openButton.isEnabled=true
                    if !self.didOpen {self.didOpen=true;self.openWorkbench()}
                } else if text.contains("需要检查") || text.contains("无法") || text.contains("不同版本") {
                    self.message.stringValue=text
                }
            }
        }
        process.terminationHandler = { [weak self] p in
            DispatchQueue.main.async { if p.terminationStatus != 0 {self?.message.stringValue="启动没有完成。请检查是否安装 Python 3.9 或更新版本、是否已有不同版本占用端口。原来的历史和桌宠没有被替换。";self?.openButton.isEnabled=false} }
        }
        do {try process.run();worker=process} catch {message.stringValue="无法运行启动程序。请检查 Python 3.9 或更新版本是否可用。"}
    }
    @objc func openWorkbench() {NSWorkspace.shared.open(URL(string:"http://127.0.0.1:8767/")!)}
    func applicationShouldTerminateAfterLastWindowClosed(_ sender:NSApplication)->Bool {true}
    func applicationWillTerminate(_ notification:Notification) {if let p=worker,p.isRunning {p.terminate();p.waitUntilExit()}}
}
if CommandLine.arguments.contains("--check") {
    let path=Bundle.main.resourceURL?.appendingPathComponent("workbench/launcher.py").path ?? ""
    guard FileManager.default.fileExists(atPath:path) else {fputs("Missing launcher\n",stderr);exit(1)}
    let process=Process()
    let runtime=Bundle.main.resourceURL!.appendingPathComponent("runtime/YukioRuntime/YukioRuntime")
    if FileManager.default.isExecutableFile(atPath:runtime.path) {process.executableURL=runtime;process.arguments=["--check"]}
    else {process.executableURL=URL(fileURLWithPath:"/usr/bin/env");process.arguments=["python3","-B",path,"--check"]}
    do {try process.run();process.waitUntilExit();exit(process.terminationStatus)} catch {exit(1)}
}
let application=NSApplication.shared
let delegate=WorkbenchDelegate();application.delegate=delegate;application.setActivationPolicy(.regular);application.run()
