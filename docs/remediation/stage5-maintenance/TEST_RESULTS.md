# 2026-11-07 本地实施测试

后续补充：用户明确授权的本地定时检查已启用，配置与首次手动核验见 [定时检查记录](SCHEDULED_CHECKS.md) 和 [机器摘要](evidence/scheduled-checks-20261107.json)。以下“未设置后台任务”描述的是首次实施交付时的历史状态；没有改变本页产品代码、包或独立验收结论。

来源提交 `7cf565b28739d4be4976daa4ae4337e06bc0ddc9`；完整来源指纹 `b328c08c8b6c7fed27afe62ae85ebc9f3303cea92767ea604d4830c0e6e776a0`。环境 macOS 27.2 arm64、Swift 6.1.2、Python 3.13.2、Node 25.8.0。测试使用人工数据与隔离 HOME；这不是完整独立用户环境。

**完整入口已连续两遍通过且数量一致，无跳过、todo、已知失败或意外通过，源码未变化。** [机器摘要与原始日志 SHA](evidence/full-checks-20261107.json)；源码证据校验器实际通过。下表数量按各测试框架报告，参数化测试中的多次输入不另行累加。

| 套件 | 每遍结果 | 具体覆盖 |
| --- | --- | --- |
| Swift | 266 通过，0 跳过 | 核心路由、编辑器、设置、时间解析；原生 UI 串行 |
| 工作台 Python | 334 通过，0 跳过 | 已有数据/解释/来源流程 |
| 发布/维护 Python | 28 通过，0 跳过 | 原发布边界及新增门槛、恢复、未知审计与失败保留 |
| 进度工具 Python | 8 通过，0 跳过 | 当前入口的进度工具 |
| 网页 Node | 55 通过，0 跳过 | 当前三份文件；含新增发送预览接收方测试 |
| 共享场景断言 | 230 PASS，其余 0 | 合成源与跨实现一致性，不能称 Windows 实机验收 |
| 真实失败探针 | 每遍 2 个通过 | 故意错误断言、过时已知问题均确实退出非零 |

合计每遍 **691 项框架测试 + 230 条共享场景断言**，另有 2 个失败探针；不能用总数替代实际功能范围。

## 单独验证的维护机制

- 零测试、未知输出、未批准跳过/known issue/todo、超时、缺失测试、变化源码、不完整/错提交/错指纹/被改日志/错包/不完整独立报告均拒绝。新测试或测试消失必须手工复核清单，不能自动认可。
- [Actions 实验](evidence/actions-lock-controls-20261107.json)：官方 v0.4.1 在线来源验证通过；离线有效/缺锁/改引用分别退出 0/1/1。GitHub 端尚未启用或验证。
- [依赖审计](evidence/dependencies-20261107.json)：10 个固定 Python 构建依赖完整审计，更新后 0 条已知公告。旧 Pillow 12.3.0 的 39 条公告记录保留原报告，不以别名重复数冒充独立漏洞数。CPython/Sparkle/所有原生库不属于这一审计结论。
- [Pillow 小实验](evidence/pillow-poc-20261107.json)：真实两个角色 idle 身体/眼皮 29 张分页，12.3.0 与 13.0.0 解码 RGBA 完全一致，均按哈希装入独立环境。
- 恢复：SQLite WAL 一致快照、记录/保存点相同、快照后新增记录保留、恢复副本继续读取且不重复、schema 999 拒绝且不写原件；错误 SHA、路径越界、符号链接越界、覆盖输出、超时与传输失败反例通过。
- [NAS 回读](evidence/nas-recovery-20261107.json)：6 文件的人工数据/证据归档 2987 字节；原件/远端/回读 SHA 一致，恢复清单一致，原件保留。当前样例没有用户真实数据。
- 受保护输入：93 项原始资源/页面中 91 项保持，只有 explanation.js 与 en.json 的接收方说明/译文为有意变化；角色素材全部保持。原整改目录 29 份未提交资料逐项哈希不变。

## 首次失败与处理（全部保留）

| 证据目录/文件 | 观察与处理 |
| --- | --- |
| 20261106 审查目录 | 发布线原布局断言失败、突发读取超限；保留历史数据，见下方历史部分 |
| maintenance-first.log | 新测试误以为所有 Python 空套件退出 0；3.13 实际为 5。修正测试夹具假设，门槛仍拒绝任何零测试 |
| product-targeted-first.log | 初次移植缺少两个 AppController 检查入口，编译失败；补入局部受控人工数据入口后重新运行 |
| layout-geometry.log / layout-third.log | 明确 1100 窗口对应 1085 视口、1050 窗口对应 1035 视口；逻辑 document bounds 并非可用内容宽度。按实际 clip 视口断言边距/列数，最终涵盖 2 语言 × 2 滚动条 × 8 宽度 |
| layout-visible.log | displayIfNeeded 实验退出 0，却无完整测试结束摘要；明确不采信，未作为通过依据 |
| web-extra-first.log | 4 项测试目标 agent-setup.js 不在当前产品，撤回本轮新复制的无适用测试；原整改资料保留。另 3 项发现现有预览接收方文案问题，已修正并通过 |
| nas-recovery/transfer.log | NAS 未开放 SFTP，默认 scp 失败；改用可复用 SSH 流传输入口，重新校验并回读通过 |
| full-checks-908d53ad | 旧的 28 项脚本测试中 NAS 失败夹具缺 summary.json；完整门槛正确拒绝且停止第二遍。修正夹具保存步骤后新提交重新完成两遍 |

上述原始文件位于本机 `~/.codex/backups/yukio-stage5-implementation-20261107/`。第一次构建的 908d53ad 包不对应最终完整两遍通过的提交，保留为过程证据，不作为本轮最终候选。

## 尚未完成的产品验收

独立首次使用/实际客户端并发/30 分钟交互仍按此前要求暂停。测试中的焦点状态和原生 field editor 不证明 WindowServer 在普通用户机器上获取焦点成功；性能读取调用也不证明实际 GUI 流畅。最低 macOS 13、Intel、正式签名/公证、真实升级路径未验；Windows 和云端 Cowork 继续暂缓。

本轮没有上传 GitHub、发布附件、启用远端保护、安装计划任务或替换现用 App；主机继续运行 Preview 2（56），产品来源 `bc95722e`。候选包与性能的实际结果见下方。

## 最终候选包与性能（已完成）

本地候选 **5.4（57）/ 工作台 0.4.9**，源码与完整测试同为 `7cf565b2`，构建目录 `~/.codex/backups/yukio-stage5-implementation-20261107/candidate-57-final/`。固定 Python 3.12.14 与依赖锁重建，未使用现用 App 或用户资料作为输入。

[包检查机器记录](evidence/package-20261107.json)：ZIP 实际解包与 DMG 只读挂载，各 491 项包内文件/内部链接/可执行位与构建清单一致；签名、DMG 完整性、源码/版本/指纹、包内资源 `--check` 均通过。挂载已退出。实际解包 App 的原生设置截图已打开检查，三栏/滚动条/底部操作可见，保持原界面。临时签名未公证，独立安装状态仍 false，不能当公开发布完成。

| 文件 | 字节 | SHA-256 |
| --- | ---: | --- |
| Yukio-5.4-maintenance.1-macOS-arm64.zip | 76845317 | `9ca6242d073ed658179584f7b3d8f73f801509c2afd56965ef9a6b2700e6d728` |
| Yukio-5.4-maintenance.1-macOS-arm64.dmg | 77258491 | `17d10ec867b4495f6c085d468a6b114a452f0f835a09df5aae44b687274e8078` |

[同机性能对照](evidence/performance-20261107.json)：两线用同一 Swift fixture，原发布线从 `2701916b` 单独取出编译；本轮在构建与其他回归结束后依次测量，每负载 3 次。表中为各次轮询最大耗时的范围。

| 负载 | 原发布线 | 本地候选 | 预设上限 |
| --- | --- | --- | --- |
| idle | 0.100–0.135 ms | 0.113–0.170 ms | 5 ms |
| normal | 15.928–17.062 ms | 0.758–1.021 ms | 25 ms |
| burst | 1530.482–1555.111 ms | 45.136–48.168 ms | 100 ms |

两组均保留事件身份/数量/顺序，候选全部符合预设读取阈值。idle 有微小波动，没有宣称所有负载都更快；normal/burst 改善明显。微基准不测 GUI 输入响应或 30 分钟连续运行。

最终 [NAS 包与证据回读](evidence/nas-handoff-20261107.json)：显式挑选 46 文件，包含候选 ZIP/DMG、构建记录、完整合成测试原始日志与摘要、性能/恢复记录；归档传输后远端与回读 SHA 相同，恢复到新目录后逐文件清单相同。路径为 `nas:/volume1/leo/yukio/maintenance/stage5-20261107/candidate-57-evidence/evidence.tar.gz`。原始包与所有失败记录继续留在本机。

## 自审与剩余边界

- 本轮为 Codex 自审，没有第二位独立评审者。检查了“退出 0 却没跑完”、旧报告配新包、重复回执关闭新问题、缺失源文件、输出覆写和私有输入混入等失败路径。
- 当前 Python 构建依赖审计通过，不把 CPython/全部原生库的安全性合并为一个绿色结论。Sparkle 2.10.1 真实更新链路仍待包验收，当前继续固定 2.10.0。
- Actions 的新增锁和暂停 Windows 的配置只在本地；真实远端强制执行与保护规则没有验证。没有设置持续后台任务；到期状态在下次维护入口运行时计算。
- 当前支持矩阵如实保留未知、暂停和暂缓。旧 agent-setup 新界面、Claude transcript/hook 特定别名等适配未整体带入。不会沿用另一分支的真实客户端结论。
- 代码提交为 `7cf565b2`；其后的本轮提交只整理入口与证据文档。核对旧测试/包时明确传入实际源码提交，仍校验当前代码指纹，不能只看版本号。

---

## 2026-11-06 历史审查记录（不代表当前实现状态）

# 本轮实测、证据与限制

2026-11-06。**当前发布线自动基准失败；本轮不是产品交付验收，第五阶段尚未完成。** 以下均为实际执行；不存在“计划测试即通过”。

## 源码与环境

| 对象 | 本轮记录 |
| --- | --- |
| 发布工作树 HEAD | `2701916b9c471d34dc11ff421b27d90cbb801248` |
| 该版本产品构建提交 | `bc95722ef6c31f2bf2ab82e4c2bee6759e9508a0`；到 HEAD 的差异为 DEVELOPMENT、FIRST-RUN、RELEASE 记录和预览更新源，产品源码相同 |
| 整改工作树 HEAD | `c344bcfc33b67705a71eef77d8c0bfcbad4d5da1` |
| 本机 | macOS 27.2 arm64；Swift 6.1.2；测试启动 Python 3.13.2；Node 25.8.0 |
| 隔离 | runner 清理继承环境、使用人工数据/独立 HOME 与偏好；仍是作者系统，不是独立环境 |
| 实际 App 元数据 | `~/Applications/Yukio.app`，5.4（56）；进程路径来自该 App。未替换/重启，不代表本轮完整包哈希核验 |

默认 `python3` 3.9.6 不满足 runner 要求，本轮实际调用已安装的 Python 3.13.2。记录绝对调用路径只为追溯，不把该作者路径写入普通用户安装流程。

## T1：发布线自动基准

在发布工作树运行现有 `scripts/run-remediation-checks.py --repeat 1 --out <新目录>`，不是改过的候选 runner。退出码 1，源指纹前后不变。失败后没有为了“通过”重复全套。

| 套件 | 实际结果 |
| --- | --- |
| Swift | 运行 248 项；一个参数化布局测试失败，12 条断言；没有跳过；耗时 22.92 秒（包含执行开销） |
| 工作台 Python | 334 项通过，0 跳过；49.93 秒 |
| 网页 | 当前发布线全部两份文件，共 52 项通过，0 跳过 |
| 共同样例 | 230 个断言通过，KNOWN_FAIL/UNEXPECTED_FAIL/UNEXPECTED_PASS 均为 0 |
| 两种现有负对照 | 故意错误断言、过时例外均被拒绝 |
| 总门槛 | **失败**，`gate_passed=false`、`product_acceptance_passed=false` |

Swift 失败位于 `YukioPlayer/Tests/YukioPlayerTests/SettingsLayoutTests.swift:50–53`。宽度 1100/1400 时右侧位置不符合断言；1050 时列位置及部分控件边界不符合预期，中英文均报告失败。保存首次日志，不把这直接称作所有真实用户的 UI 故障。

**报告字段缺陷**：runner 的 `full_suite=true` 仅表示未选择 probe-only，不表示所有仓库测试均被覆盖；本轮发现它没有执行 `scripts/test_*.py`，也不能将此字段当成完整验收。

## T2：针对性复核与漏测补跑

复用现有 runner 的隔离环境和超时/计数功能，在新的 `supplemental` 目录执行：

```sh
python3.13 -m unittest discover -s scripts -p 'test_*.py' -v
swift test --no-parallel --filter SettingsLayoutTests
```

第一条在发布仓库根目录执行，第二条在其 `YukioPlayer` 执行；不是在真实 HOME 下直接重复 UI 操作。

- 发布/构建脚本：14 项通过，0 跳过，2.41 秒。
- 定向布局：1 个参数化测试失败，6 条英文断言；1.55 秒。首次全套是中英文共 12 条。失败重现，但两次观察范围不同，可能涉及测试顺序/全局状态/布局环境，原因仍待定位；没有将失败数量差异解释为已确定的根因。
- 未放宽断言，未修改生产布局或测试。下一步应检查窗口/scroll view 实际尺寸、布局刷新时序、设置隔离及系统差异，并用真实 UI 验证。

## T3：只读静态审查与门槛实验

实际执行 [audit_snapshot.py](experiments/audit_snapshot.py)，读取两条代码线、工作流和 runner。它从真实 Python AST 取出每轮 `passed` 判断表达式，输入 `exit_code=0, tests=2, skipped=1`，其余条件为真；**两条线均返回通过**。这验证的是跳过门槛缺失，未声称本轮真实套件有跳过。

复现：

```sh
python3.13 docs/remediation/stage5-maintenance/experiments/audit_snapshot.py \
  --published <发布工作树> --remediation <整改工作树> --out <新的JSON文件>
```

其他核查：发布线已有两份网页测试均被选择，整改线另有 `test_agent_setup_ui.cjs` 和 `test_explanation_ui.cjs` 尚未移植；三份发布脚本测试不在统一入口中。两条线 workflow 无 action lockfile、使用可变标签；portability 工作流仍包含 Windows runner 和浮动 PyInstaller 范围。本轮没有执行任何远端 workflow。

## T4：同样例读取性能对照

使用整改线原有 `tests/remediation/source-benchmark/main.swift`，分别与两线全部 `YukioCore/*.swift` 用 `swiftc -O ... -lsqlite3` 编译。二进制输出到新的证据目录，各自只读写自身人工日志。两线顺序运行，没有并行压测；每条线 idle/normal/burst 各三遍、每遍六轮。normal 每文件每轮新增 10 条；burst 四文件一次共 4,000 条。记录所有源文件 SHA、fixture SHA、系统与 Swift 版本，完整命令方案见下方。

事前沿用原项目阈值：idle 5 ms，normal 25 ms，burst 100 ms；未在结果出来后放宽。

| 单轮最大耗时 ms（每类三遍） | 发布线 | 整改线 |
| --- | --- | --- |
| idle | 0.195 / 0.136 / 0.105 | 0.140 / 0.122 / 0.105 |
| normal | 17.126 / 15.704 / 15.700 | 0.887 / 0.776 / 0.783 |
| burst | **1529.286 / 1542.415 / 1539.397** | 46.360 / 48.245 / 47.505 |
| 原阈值 | burst 3 次失败，其他 6 次通过 | 9 次通过 |
| 事件数量、身份及会话内顺序 | 9 次均通过 | 9 次均通过 |

这是同机主线程读取调用的比较，不是 GUI 输入、动画、内存/能耗、最低系统或独立环境验收。两线同时有其他差异，不能声称已证明某个单一补丁的全部收益；下一步应在发布线上做单因素移植/前后对照。

可复现编译/运行模板（路径换成此次新证据目录，不覆盖）：

```sh
swiftc -O -o <发布证据目录>/reader-benchmark \
  <发布工作树>/YukioPlayer/Sources/YukioCore/*.swift \
  <整改工作树>/tests/remediation/source-benchmark/main.swift -lsqlite3
# 每个 mode 各运行 3 次，每次使用不同的新目录。
<发布证据目录>/reader-benchmark <新人工数据目录> idle
<发布证据目录>/reader-benchmark <新人工数据目录> normal
<发布证据目录>/reader-benchmark <新人工数据目录> burst
```

对整改线同样编译/运行。每次统计 `polls[].total_ms` 的最大值，并要求 `identity_and_order_passed=true`。原始每轮值保存在下列 JSON，不能只保留表中四舍五入值。

## T5：存储/来源检查

NAS 使用 `ssh -p 1529 -o BatchMode=yes -o ConnectTimeout=8 nas`，权限检查和 `df` 返回成功；`/volume1/leo` 可用约 4.1 TiB。这里只验证连接和权限声明，**没有写入/传输/回读测试**，不叫归档验收通过。

本机剩余空间约 1.4 TiB；本轮无大包下载/生成。原有修改/未跟踪文件共 29 份有 SHA 快照，审查产物单独保存；没有整理/删除历史工作树或数据。

## 已保存证据

| 文件 | 内容 |
| --- | --- |
| [published-baseline.json](evidence/published-baseline.json) | 原 runner 总结果、源指纹、版本、计数、负对照和失败状态 |
| [supplemental.json](evidence/supplemental.json) | 14 项补跑与定向布局复测结果 |
| [audit.json](evidence/audit.json) | 两线源码/工作流审查和跳过门槛实验 |
| [reader-comparison.json](evidence/reader-comparison.json) | 两线每个源码文件 SHA、人工负载、18 次运行的逐轮值 |
| [sha256.json](evidence/sha256.json) | 上述四份证据的 SHA-256 |

原始全量日志、隔离配置和编译结果：`~/.codex/backups/yukio-stage5-maintenance-20261106/`，子目录 `published-baseline`、`supplemental`、`reader-comparison`。公开可提交目录仅复制合成摘要，不含用户数据库、配置、登录或实际聊天正文。这个目录还没有上传。

收尾检查：26 个本地文档链接有效，四份证据哈希一致，原有 29 份修改/未跟踪文件哈希全部保持，发布工作树仍干净。审查脚本语法检查与 `git diff --check` 通过。实际新增范围为本目录和 DEVELOPMENT 的两行入口说明；状态列表中其他既有修改不属于本轮成果。

## 批判性自审与未验证项

- 检查发现补跑全绿仍不能使 Swift 失败消失；摘要保持总失败。
- 当前布局复测错误数量变化，尚不能归为“偶发测试”并跳过；需要定位真实契约和隔离条件。
- 现有读取优化在另一条线有效，但尚未证明可以无差异移植；保留受保护 UI 和格式回归。
- 没有运行实际候选包安装、真实助手调用、多聊天输入、完整 30 分钟交互、更新失败恢复、SQLite 恢复、漏洞扫描、云端 CI 负例、公证或独立评审。这些全部保留为后续任务。
- 本轮批判性复核来自同一执行者；不是另一位评审者或另一台系统的独立结论。

研究/方案可供用户审查；“长期维护机制已实现”与“第五阶段全部完成”均不成立。
