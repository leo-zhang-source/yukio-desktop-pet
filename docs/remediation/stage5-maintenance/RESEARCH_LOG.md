# 外部研究记录

检索/访问：2026-11-06（America/Los_Angeles）。只采用官方、一手论文与项目仓库。发布日期、网页最后更新日期与本次访问日期分开记录；未标注发布日期的页面不猜日期。本轮没有把搜索摘要当成本项目实测。

## 来源、适用条件与决定

| ID | 一手来源与日期 | 已核实的要点 | 对 Yukio 的适用与限制 |
| --- | --- | --- | --- |
| R1 | [DORA 2025 报告](https://dora.dev/research/2025/dora-report/)（2025，索引未注明具体日）；[Small batches](https://dora.dev/capabilities/working-in-small-batches/)（页面未注明日期） | 强调组织系统与小批量反馈对 AI 辅助开发的影响 | 支持逐主题改动和复核；组织层研究不能推导本项目效率提升百分比，也不要求每次小改动立即上传 |
| R2 | [An Empirical Study of the Evolution of GitHub Actions Workflows](https://arxiv.org/abs/2602.14572v3)（初稿 2026-02-16，v3 2026-03-01；页面列出 JSS 期刊记录） | 研究 49K+ 仓库与 3.4M+ 工作流版本，工作流维护多为小范围配置变化 | 维护脚本与 CI 本身也需版本/检查；样本结论不是 Yukio 运行证明 |
| R3 | [Systemic Flakiness](https://arxiv.org/abs/2504.16777)（2025-04-23） | 在 24 个 Java 项目、810 个不稳定测试中分析共同失败原因 | 用于“保留首败、查环境/共享状态”的方法；不能用 Java 统计解释本轮 AppKit 布局失败，不能称该失败已确定为 flaky |
| R4 | [The Design Space of Lockfiles Across Package Managers](https://arxiv.org/abs/2505.04834v3)（初稿 2025-05-07，v3 2025-10-27） | 比较 7 种包管理器，锁文件设计和维护存在差异 | 支持同时记录解析结果与输入；未研究本项目 Swift/pip 具体锁法，实施依官方文档，不直接套用论文结论 |
| R5 | [GitHub Actions lockfiles GA](https://github.blog/changelog/2026-10-28-github-actions-workflow-lockfiles-are-generally-available/)（2026-10-28）；[官方机制](https://docs.github.com/en/actions/concepts/security/workflow-dependency-lockfiles)；[工具 v0.4.1](https://github.com/github/gh-actions-lock/releases/tag/v0.4.1)（2026-11-02） | 支持锁定 action 及传递 action，逐工作流采用；官方工具生成；可校验过期；不锁 reusable workflow 调用、runner 镜像或其他输入 | 值得做 Mac 工作流 PoC；发布很新，不能据“GA”断言本仓库验证完成。上传/启用须单独获准 |
| R6 | [GitHub secure use](https://docs.github.com/en/actions/reference/security/secure-use)（滚动文档，未注明发布日期）；[SHA pinning policy](https://github.blog/changelog/2025-08-15-github-actions-policy-now-supports-blocking-and-sha-pinning-actions/)（2025-08-15） | 完整提交 SHA 固定和最小权限是成熟控制；新版 lockfile 是覆盖传递 action 的替代方案 | lockfile 未验证前可用 SHA 方案；锁定不保证所锁依赖本身无恶意或漏洞 |
| R7 | [Sparkle 官方文档](https://sparkle-project.org/documentation/)（滚动文档）；[2.10.1 发布](https://github.com/sparkle-project/Sparkle/releases/tag/2.10.1)（2026-10-25） | 区分应用签名、公证、更新归档/列表验证；2.10.1 修复 NFC Unicode 路径提前安装等问题 | 已有 Sparkle 2.10.0 应单独做路径/升级影响评估；尚未复现 Yukio 受影响，未升级，也未认定安全漏洞 |
| R8 | [pip Secure installs](https://pip.pypa.io/en/stable/topics/secure-installs/)（本次为 v26.3 文档，未注明页面发布日期） | 全依赖固定与 `--require-hashes`、禁止源码包的安装方式；完整性与可重复输入各有边界 | 保留现有构建方式，检查旁路入口；不更换包管理器，不把锁定当漏洞扫描 |
| R9 | [PyPA pip-audit](https://github.com/pypa/pip-audit)；[v2.10.1](https://github.com/pypa/pip-audit/releases/tag/v2.10.1)（2026-06-10） | 维护中的已知漏洞审计工具；可输出跳过原因；不检测恶意软件，也不覆盖所有随包原生库漏洞 | 候选构建环境只读审计，工具另锁定，不使用自动修复；离线失败记未知，补 CPython/Sparkle/原生库上游公告复核 |
| R10 | [Dependabot options](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference)；[Renovate 官方仓库](https://github.com/renovatebot/renovate)及[发布记录](https://github.com/renovatebot/renovate/releases)（滚动页面，未注明统一发布日期） | 支持依赖更新自动化及配置管理，Dependabot 可分组和控制打开的 PR 数 | 对比后优先减少运维：本地评估先落地，远端原生方案后评估；自定义需求再考虑 Renovate。没有启用任何 bot |
| R11 | [Apple Improving app responsiveness](https://developer.apple.com/documentation/xcode/improving-app-responsiveness)及[响应机制](https://developer.apple.com/documentation/xcode/understanding-user-interface-responsiveness)（滚动文档，未注明日期） | 离散交互约 100 ms 与连续渲染刷新间隔是不同约束；非 UI 工作不应长期占据主线程 | 历史 burst ≤100 ms 不是动画流畅标准；要同时测读盘解析与用户可见响应，不能用后台线程数量当性能成果 |
| R12 | [Apple WWDC26：Profile, fix, and verify](https://developer.apple.com/videos/play/wwdc2026/268/)（WWDC 2026，页面未标具体日） | 用 Instruments 的采样/跟踪、定位、修复、复验循环检查性能 | 适用于后续真实 Mac 包；工具依 Xcode/系统支持，本轮未执行 Instruments，不伪造 trace |
| R13 | [SQLite Online Backup API](https://sqlite.org/backup.html)（页尾更新 2025-11-13） | 可生成一致性快照；并发写可能让备份重新开始甚至长期不完成 | 采用有超时/失败记录的备份实验；快照不自动包含备份后的新增数据，回退须另保留新增内容 |
| R14 | [SLSA v1.2 发布](https://slsa.dev/blog/2025/11/announce-slsa-v1.2)（2025-11-24）；[Build track](https://slsa.dev/spec/v1.2/build-track-basics) | 来源证明与托管签名/强化构建是不同级别 | 扩展已有 source/build manifest 来绑定证据；不声称本地 JSON 即达到 SLSA L2/L3 或正式认证 |
| R15 | [NIST SSDF 1.1 final](https://csrc.nist.gov/pubs/sp/800/218/final)（2022-02）；[SSDF 1.2 initial draft](https://csrc.nist.gov/pubs/sp/800/218/r1/ipd)（2025-12-17） | 将安全开发、交付及漏洞处理融入生命周期；读取的 1.2 页面仍标 Initial Public Draft | 采用成熟生命周期思路，持续关注草案；不把草案说成已生效规范，不增加项目认证承诺 |
| R16 | [Apple Notarizing macOS software](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)（未注明发布日期） | 公证是自动扫描/签名检查，和 App Review、功能验收不同 | 正式签名、公证、实际下载首次启动分别记录；没有证书/账号时保留未完成，不绕过系统保护 |

以上发布项目的具体日期以官方 Release 页及公开 GitHub Releases API 交叉核实。报告没有依据第三方新闻/转载作技术决定；没有下载或上传私人代码给外部研究服务。

## 冲突与交叉核查

1. **“固定 SHA”与“采用 lockfile”**：不是忽略旧官方建议。2026-10-28 的新能力提供 action 传递依赖覆盖，但仍有 runner/reusable workflow 边界。方案先小范围验证，保留完整 SHA 后备；不能手工伪造 lockfile。
2. **“小步改动”与“集中上传”**：DORA 关注反馈和批量大小；用户要求集中且显式授权上传。采用小本地主题/验证、少量审查后交付，不以研究替代上传许可。
3. **“历史性能通过”与“本轮性能失败”**：本轮实测发布线约 1.53 秒、整改线约 47 ms，针对不同源码。并无矛盾；同源、同样例、同环境的关联才有意义。跨线对照不是单因素因果实验。
4. **“<100 ms”与“动画流畅”**：Apple 明确区分离散响应和连续渲染；项目旧基准只验证调用耗时。沿用旧基准用于回归，同时新增实际 GUI 观察，不能降低验收口径。
5. **“有锁/有扫描”与“安全”**：锁文件限制输入漂移，审计只覆盖已知范围，签名/公证又是另一个维度。报告分别输出“通过/发现问题/未知/未运行”，避免统一绿色掩盖缺口。

## 研究转为实验与后续任务

已执行：现有 runner 的跳过门槛实验、两线静态审查、发布线自动回归/首败复测、同样例性能对照。结果见 [TEST_RESULTS](TEST_RESULTS.md)。

待批准后执行：一项真实修复走完维护任务卡；错误证据拒绝实验；Actions lockfile 与 SHA 备选 PoC；依赖审计；SQLite 人工数据恢复；候选包并发与性能验收。尚未完成的实验不作为选型已落地的依据。

## 2026-11-07 实施中追加研究与决策

- **Pillow 13.0.0**：[官方发布说明](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html)，2026-10-16；[维护者安全公告](https://github.com/python-pillow/Pillow/security/advisories/GHSA-78g4-xqwv-q3g8)，2026-10-17；[PyPI 固定版本元数据](https://pypi.org/pypi/pillow/13.0.0/json)。实际 pip-audit 2.10.1 对旧锁报告 39 条公告记录（不同 ID/别名可能指向同一问题，不能称 39 个独立漏洞），均集中于 Pillow 12.3.0。官方资料交叉确认 JPEG2000 等解码路径修复于 13.0.0。项目用途是维护者图像分页/打包，当前没有据此证明 App 中任意不可信图片可触发漏洞。
- **决定**：只升级 Pillow；cp312 arm64 wheel SHA `fc481f742ccda20e9ed760b8f978dff50f2a4e9bc253ac167fb0a05b0783ef52` 来自 PyPI，实际安装按哈希验证。13.0.0 要求 Python >=3.11，固定构建 Python 3.12.14 符合；wheel 最低 macOS 11，实际包仍检查 macOS 13 限制。两个角色的 idle 身体/眼皮共 29 张分页逐像素对照相同；升级后 10 个锁定 Python 依赖审计 0 条已知公告，完整包构建另记。这不是原生库或所有未来漏洞的安全担保。
- **Actions lock 实验**：官方 `github/gh-actions-lock` v0.4.1 生成并在线验证 Mac 工作流锁；有效、缺锁、引用改为不存在版本的离线检查分别退出 0/1/1。保留 lockfile 路线，无需退回手写 SHA。官方工具的 `--verify-local` 只检查覆盖，不能代替在线出处与实际 GitHub 强制执行。
- **维护工具可重建性**：pip-audit 及 26 个解析到的依赖记录到独立哈希锁，另建干净 venv 完整 `--require-hashes --only-binary=:all:` 安装。工具不进入用户安装包。
- **布局实验修正**：AppKit 未显示的 scroll/document 几何可在初始状态有不同逻辑宽度；有效合同是卡片处于实际 clip 视口、边距和分栏符合可用宽度。额外 `displayIfNeeded` 实验退出 0 但未产生完整 Swift Testing 总结，明确不采信，保留日志。最终测试不凭退出 0 放行。
