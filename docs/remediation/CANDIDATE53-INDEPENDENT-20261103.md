# 候选 53：长时间待答与重启恢复

2026-11-03（America/Los_Angeles，证据 UTC 2026-11-04）。本地候选，未上传 GitHub，未替换主机 App；Windows 按用户决定暂缓。沿用独立 Tart macOS 26.6.2（25G83）arm64 和用户在 VM 自行登录的 Claude Desktop 4.16336.0；与宿主只共用硬件和网络，不借用宿主登录、钥匙串或文件。

## 问题与修复

候选 52 中，真实 B 聊天的问题一直未回答，但原生启动只回放最近 15 分钟的记录，且普通未结束工具会在 30 分钟后视为失联；工作台仍 waiting，原生却回到 idle。现场见 `vm52-visible-B.json` 与 `vm53-before-restore-B-unanswered.png`。

候选 53 只从本地 Claude 转录的有界末尾恢复明确未答问题，要求窗口内有完整的当前轮次开始，原始会话、调用编号和问题正文均明确；保留原时间，不回放普通旧工作。结果、取消、结束、新一轮、歧义结果、跨会话记录、缺失轮次和未写完的结果均不恢复。已跟随的明确问题不再套用普通工作超时，仍由回执、取消、新轮次或来源消失清除。现有限制仍为最近 24 小时发现的文件、末尾 1 MiB；超出窗口缺少依据时不猜测恢复。

源码 `1046be5032aacce87cabf0af7703dae8b43a3e5b`，5.4（53），工作台 0.5.6。新增 7 项恢复／超时回归；完整入口连续两遍均为 Swift 285、Python 334、发布 13、Node 64，加共用断言 230，全通过、无跳过、两个故意错误均被拒绝。两遍源码指纹 `10bc3aa296d0030f017f477885df21c4a575eeda431bbf5291d5d8ee6f0aad94` 与提交后一致。

首次完整检查曾因既有输入测试窗口未取得系统键盘焦点而失败，现场和后续定位日志均保留。焦点策略单元测试改为真实 AppKit 编辑器加受控的窗口焦点输入，显式检查前提，并覆盖恢复、自有窗口失去焦点及其他编辑器，未修改产品输入逻辑。此项只证明策略分支，不宣称 WindowServer、中文输入法或真实点击已通过；实际包输入另记。

## 实际包

DMG 77,250,997 字节，SHA-256 `9cd1b52f48b4c21e9891297a943cdebf479d5bc5a1db53371d8d7d09c630c14a`；ZIP 76,842,155 字节，SHA-256 `9db6510053c99bcee6c9273adbf01540324ad6f990e4dab8003a4157aae02a66`。从只读挂载 DMG 安装到 `/Users/admin/yukio-qa-53/Yukio.app`，490 项文件／链接／权限匹配，严格签名、原生和冻结工作台检查通过。仍为临时签名、未公证、`public_release_ready=false`，未移除 quarantine。

## 实际 GUI 结果

- 真实 B 问题已等待约 75 分钟，53 启动后恢复正确题目与 GAMMA／DELTA 选项；原生为 `question_for_user`，没有旧完成牌。工作台仍为 Waiting 1／Working 0，两端一致。
- B 创建时尚未安装回答通道，实际发送 `B53_UNSENT` 得到明确失败提示后，不再点击输入框，继续输入 `_ok`，显示完整 `B53_UNSENT_ok`，没有假装送达。
- 通过 VM 系统设置安装拼音简体输入源。实际出现 `nihao` 候选窗口；组合输入时 Escape 只取消组合，不发送、不关闭卡片。提交中文后 Escape 关闭卡片，菜单重开保留 `你好世界`，共核对 4 次关闭重开。
- B 与新 C 同时等待，分别输入 `你好世界`、`测试成功`，逐次截图确认 9 次手动切换草稿正确。第 10 次前后 C 的真实 hook 达到 570 秒期限，出现新的批准请求；不把未核对的切换记为通过。旧草稿没有被提交为批准。
- 超时后回到同一原始问题时，C 草稿没有接续：回答通道编号和原始工具编号使用了不同界面身份。这是实际发现的缺口，已进入[候选 54](CANDIDATE54-INDEPENDENT-20261103.md)，本候选不宣称 MC-03 关闭。
- 在完整请求复核对话框中仅允许本次 AskUserQuestion，然后在 Claude 原始界面提交 C_ONE。C 正常结束，B 仍等待且中文草稿完整。B 原 47 条不变；旧 Codex 244／Claude 331 条逐条哈希不变，Claude 新增 22 条至 353，无重复事件。

本候选临时签名改变后辅助功能实际为未授权，以上结果不用于声明可见聊天识别通过；候选 52 的授权和可见性证据单独保留。

## 证据与边界

私有证据根目录 `/Users/leozhang/.codex/backups/yukio-stage1-5/20261101T185459Z`：`candidate53-final-checks/`、`candidate53-validation-identity.json`、原始失败的 `candidate53-checks/` 及 `candidate53-question-drafts-*.log`、`candidate-53/`、`vm53-package.json`、`vm53-history-before.json`。安装前记录数量 Codex 244／Claude 331／Deep Code 0。

实际结果见 `vm53-acceptance-summary.json`、`vm53-input-failure-result.json`、`vm53-draft-switch-evidence.json`、`vm53-draft-reopen-*.png`、`vm53-C-after-switches.json`、`vm53-C-finished-B-draft-preserved.png`、`vm53-workbench-B-waiting.png`、`vm53-history-preserved.json`。NAS 固定归档为 `nas:/volume1/leo/yukio-validation/2026-11-03/candidate53-restore-20261104T043344Z`；25 个文件、233,757,291 字节，远端和完整读回 SHA-256 匹配，恢复源码 2,526 项、App 490 项与严格签名通过。记录在 `candidate53-nas/receipt.json`，不覆盖 51／52 的原始归档，不删除本地原件。

本候选不补足[已实测的云端 Cowork 接入缺口](CANDIDATE51-52-INDEPENDENT-20261103.md)。完整 MC-01–08、父子任务、最低系统／Intel／多屏、公开更新与正式签名仍按各自证据保留待完成，不能把局部真实测试扩展为全部阶段关闭。
