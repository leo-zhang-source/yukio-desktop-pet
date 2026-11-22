import Foundation

enum WorkbenchDisplayMode: String, CaseIterable {
    case window
    case quickLook

    static let preferenceKey = "workbenchDisplayMode"

    init(preference: String?) {
        self = preference == "fullScreen" ? .window : preference.flatMap(Self.init(rawValue:)) ?? .quickLook
    }

    func title(chinese: Bool) -> String {
        switch self {
        case .window: return chinese ? "常驻窗口" : "Keep open"
        case .quickLook: return chinese ? "快速查看" : "Quick view"
        }
    }

    func detail(chinese: Bool) -> String {
        switch self {
        case .window:
            return chinese ? "普通窗口，点击工作台外部仍保持打开。" : "Stay open when you click outside the workbench."
        case .quickLook:
            return chinese ? "临时浮窗，点击工作台外部立即收起。" : "A floating window. Click outside to dismiss."
        }
    }
}
