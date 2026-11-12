# 第五阶段：本地长期维护入口

2026-11-11 补记：57–62 版的本地维护与修复已按用户明确要求集中交付为 Preview 3（63），补充 Python 3.12.16；两遍检查每遍 728 项测试与 230 条共享断言通过，公开包匿名下载验签、桌面更新和 NAS 回读完成。本次源码、文档、远端检查与限制见[集中交付记录](../RELEASE-54-PREVIEW3.md)。下文 11 月 7 日的“未上传”是历史状态。M6 仍暂停。

2026-11-07。用户已批准路线 B，M0–M5 的本地维护机制已实施并完成相应验证，产品基于 Preview 2。本轮只在本地开发、验证和准备候选；没有 GitHub 上传、远端发布或现用 App 替换。完整独立首次使用验收继续暂停，Windows/云端 Cowork 继续暂缓。

完整两遍通过：每遍 691 项自动测试 + 230 条共享场景断言，0 跳过；实际 ZIP/DMG 内容与来源已核验，本地候选为 5.4（57）。首次失败、修复过程和范围限制均保留在测试记录中。

用户随后要求的 [定时维护检查](SCHEDULED_CHECKS.md) 已启用，2026-11-08 改为每 60 小时（两天半）触发。每次检查到期状态，7/30/90 天复核周期保持不变，通知设为仅失败；不自动升级、发布或上传 GitHub。11 月 8 日首次实际定时轻量检查已通过；新间隔的实际触发与提醒投递仍待后续真实运行验证。

从 [维护手册](MAINTENANCE.md) 开始；[实施记录](IMPLEMENTATION.md) 解释改动与真实任务卡；[测试结果](TEST_RESULTS.md) 区分已验证与未覆盖项；[资料地图](STORAGE.md) 说明恢复路径。每次任务先运行 `scripts/maintenance.py check`，每次改动用现有测试入口验证，证据目录不得覆盖。

| 唯一登记 | 作用 |
| --- | --- |
| [maintenance/policy.json](../../../maintenance/policy.json) | 当前范围、复核责任/到期日、锁文件认可值、开放问题 |
| [test-inventory.json](../../../maintenance/test-inventory.json) | 五套测试的明确文件清单，与实际发现逐项核对 |
| [dependencies.json](../../../maintenance/dependencies.json) | 固定依赖、用途/许可证、原生运行时与审计范围 |
| [compatibility.json](../../../maintenance/compatibility.json) | 实际平台/客户端证据与暂停、未知、未支持范围 |
| [action-pins.json](../../../maintenance/action-pins.json) | 官方生成 Actions 锁的复核来源；不是远端已生效证明 |

[架构决策](ARCHITECTURE.md) · [路线与验收](ROADMAP.md) · [项目审查](PROJECT_OVERVIEW.md) · [研究记录](RESEARCH_LOG.md)

2026-11-06 的只读审查及失败数据保留在 [测试结果的历史部分](TEST_RESULTS.md) 和 evidence；它们不能替代当前提交的通过证据。当前原始证据目录为本机 `~/.codex/backups/yukio-stage5-implementation-20261107/`，不是用户 App 的运行依赖。

机制本地完成与第五阶段完整产品验收是两种结论。独立实际包验收未恢复时，不宣布 G5 全部关闭；后续上传仍需要当次明确授权。
