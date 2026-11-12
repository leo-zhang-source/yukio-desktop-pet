> 本页保留 2026-11-06 审查/研究快照。2026-11-07 用户已批准本地实施；当前实现与验证以 [实施记录](IMPLEMENTATION.md)、[测试结果](TEST_RESULTS.md) 为准。

# 项目审查快照

2026-11-06。事实来自本地源码、提交、现用 App 元数据、历史交付记录及本轮测试。状态仅适用于记录的提交和环境。

## 目标与实际范围

Yukio 是面向普通用户分发的 Mac 桌面角色与活动工作台。它读取用户自己的助手活动，展示状态/聊天/问题，支持后台回答、解释、提醒、设置、语言与皮肤。用户自行安装并登录外部助手；私有 NAS、作者账号和局域网模型不能成为产品运行条件。

本轮按原“分阶段整改计划”的第五阶段及 [STAGE5-CONCURRENCY](../STAGE5-CONCURRENCY.md) 工作。Windows 与云端 Cowork 暂缓；本地 Code、多聊天、多 Agent 和解释隔离仍在范围内。此次没有上传授权，也没有提前批准大规模实施。

## 三类来源不能混用

| 对象 | 位置与标识 | 当前用途 |
| --- | --- | --- |
| 指定整改入口 | `~/.codex/worktrees/yukio-remediation/yukio-cloud-handoff`，`codex/remediation-baseline`，`c344bcfc33b67705a71eef77d8c0bfcbad4d5da1` | 审查入口、历史整改成果、未提交资料；本轮文档保存在这里 |
| 当前发布产品线 | `~/.codex/worktrees/yukio-54-release/yukio-cloud-handoff`，`codex/mac-54-preview-release`，`2701916b9c471d34dc11ff421b27d90cbb801248` | Preview 2（56）；产品构建提交 `bc95722ef6c31f2bf2ab82e4c2bee6759e9508a0`；后续 3 个文件/更新源的差异不改变本轮测试的产品源码 |
| 实际安装 App | `~/Applications/Yukio.app`，5.4（56） | 本轮读取 Info.plist 并确认运行进程来自此处；没有重新做完整包清单一致性验收 |

发布记录见另一产品线的 `docs/remediation/RELEASE-54-PREVIEW2.md`。当前整改文档顶端仍记录 Preview 1；差异不能靠全目录覆盖消除。对 `YukioPlayer/Sources`、`tools/activity-workbench`、`scripts`、`.github` 的两线比较有 77 个文件变化，其中包括布局、状态、测试、构建与版本配置。

用户给定的独立 `Desktop/Yukio 规划` 路径本轮未找到；原计划实际位于保留目录 `Desktop/yukio-cloud-handoff/Yukio 规划/Yukio-分阶段整改计划-2026-10-26.md`，已读取第五阶段全文。没有移动原资料。

## 技术结构与依赖

| 层 | 当前职责 | 关键边界 |
| --- | --- | --- |
| `YukioPlayer/Sources/YukioCore` | 来源解析、事件身份、路由、问题状态、动画时间 | 状态按来源/会话/轮次/调用归属；不得凭标题关联 |
| `YukioPlayer/Sources/YukioPlayer` | AppKit 窗口、设置、焦点、回答桥、后台拥有关系 | 主线程更新 UI，退出只结束自有进程 |
| `tools/activity-workbench` | Python 本地 HTTP、查询、解释、逐用户授权；JS/CSS 经 WebKit 显示 | 仅本机服务；自己的助手配置；草稿/异步结果按聊天隔离 |
| `tools/activity-workbench/core/yukio` | 来源采集、SQLite 历史、保存点、格式兼容 | `ActivityHistory` 用事务/应用标识/模式版本保护数据库，现支持 1、2；拒绝未知模式版本 |
| `scripts/build-macos.py` | 指定提交导出、固定依赖、原生编译、工作台冻结、资源与包清单 | 构建独立于用户已装 App；不安装、不发布 |
| `scripts/run-remediation-checks.py` | 合成数据及隔离偏好下的 Swift/Python/网页/共同样例检查 | 本机自动测试，不能充当独立安装验收 |

Swift Package 要求 tools 5.9；测试环境约定 Swift 6.1+。发布线锁定 Sparkle 2.10.0、CPython 3.12.14、PyInstaller 6.22.3、dmgbuild 1.6.7 及带哈希的构建依赖。整改线的依赖说明与锁文件仍是 dmgbuild 1.6.5。依赖记录必须按产品线更新，不以文件修改时间选“最新”。

Mac 正式构建借用 `YukioWin/scripts/prepare-windows-assets.py` 做无损分页；这是 Mac 的构建依赖，不能因 Windows 暂缓而删除。动画正式输入和已验收资源本轮不改动。

## 已有成果与技术债

- 已有固定提交构建、依赖哈希、包清单、两种错误探针、重复检查、任务卡以及多聊天验收矩阵；可直接扩展。
- 发布线 `main.swift` 2566 行、`ActivityRouter.swift` 816 行，职责较集中；行数只是盘点，不构成重写依据。先处理设置/问题状态/读取的一个边界，并保留行为测试。
- 发布线缺少整改线已有的部分状态/读取优化与新增测试；目前是双线漂移，不是一个可直接合并的补丁。
- runner 的指纹范围没有覆盖发布线全部 `scripts/` 与 `config/`；未拒绝跳过；发布脚本测试未进入统一执行。已有负对照只覆盖共同样例，不能证明其他门槛无缺口。
- 现有 Actions 使用 `@v4`/`@v5` 可变标签，无 `actions.lock`；portability 工作流有 Windows runner 和浮动 PyInstaller 范围。静态配置与暂停 Windows 的政策不一致，未声称该工作流本轮实际运行。
- 未发现统一依赖维护/漏洞处置/兼容到期记录。锁定依赖保护输入一致性，不说明没有漏洞。没有运行完整漏洞扫描。
- 新手/发布/整改文档存在历史快照交错；应保留历史，并给当前事实唯一入口。

## 当前真实限制

本轮环境为 macOS 27.2 arm64、Swift 6.1.2、Python 3.13.2、Node 25.8.0；默认 `python3` 是 3.9.6，不满足现有 runner 要求。后续入口应提前检测并给出正确依赖说明，而非借用作者私有 Python 路径。

完整首次使用独立验收在 2026-11-04 被用户暂停。Preview 2 修复包的独立界面复验、登录后真实任务、完整 MC-01–08、30 分钟真实交互、完整升级/失败恢复尚不能记通过；最低 macOS 和 Intel 也无当前充分证据。历史候选 49–54 的有限 VM 结果不能迁移成 Preview 2 的通过结论。

发布记录说明 App 为临时签名、未 Apple 公证；本轮未重新枚举证书或改变签名。原发布与桌面核对有历史证据，本轮只补充元数据/运行路径检查。仓库统一项目许可未见，不能擅自指定许可证。

NAS 经指定端口 1529 可达，`/volume1/leo` 权限检查可写、可用约 4.1 TiB；本轮未做写入/回读演练。大包后续直存任务子目录并核验，原件保留。新审查产物较小，保存在本地；既有 29 份修改/未跟踪文件另有哈希快照以防误改。
