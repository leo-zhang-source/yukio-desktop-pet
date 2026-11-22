# Mac 5.4 Preview 5 · 集中交付

2026-11-21。用户明确要求整理最新更新并上传 GitHub。执行者为当前 Codex；代码与资料复核为自审，没有冒充独立评审。

## 本次任务卡

- 起点：公开 main `21b3bcbad816344536394686506966bd451ac4cd`；桌面 5.4（66.7）产品源码 `0a59165a4847213f2a913f1c1a94ab17269cca0e`；维护入口 `b5493a9edc451705ef728bc44ac2dc1c3fdc0239`。
- 发布：5.4 Preview 5（66.8）／工作台 0.4.17，来自现用 66.7 产品线，补齐发行配置和双语指南。目标为 `leo-zhang-source/yukio-desktop-pet` 的 main；完整维护候选源码另同步维护分支，不能用候选整包替换现用产品。
- 内容：[发布说明](../releases/5.4-preview.5.md)。本地过程提交与旧包保留，远端使用审查后的汇总提交，不改写已发布历史。
- 检查：本机两遍后台范围检查；GitHub Mac runner 执行完整两遍检查；固定提交构建、ZIP/DMG 清单和签名、匿名下载、安装与运行进程核对。
- 回退：备份原 66.7 App，只替换应用文件；不恢复旧数据库覆盖新增记录，不改变助手账号与配置。

## 验收边界

本机不运行会抢焦点、切桌面或进入全屏的检查。前台原生全屏/快速切换、实际聊天跳转和独立环境的普通安装、首次使用及真实多客户端矩阵保留待验。远端源码回归不是实际安装包的独立首次使用验收。本版继续是预览版，未 Apple 公证。

维护线额外的 67–69 候选记录仍按各自产物理解；它们的通过或失败不能归给 66.8。Windows 与云端 Cowork 按用户决定暂缓。

## 实际结果

产品提交固定为 [`3451c000264b4c63a54abc5e892fd5a46c8da0c8`](https://github.com/leo-zhang-source/yukio-desktop-pet/commit/3451c000264b4c63a54abc5e892fd5a46c8da0c8)，标签 `v5.4-preview.5`。后续交付记录和签名更新源只修改文档/更新信息，不修改包内产品。源码指纹 `b9bf31f4befa60c1a27a4fbb1dc25b7badc62babe2f3a6793dee5d69f9213044`。

| 核对范围 | 实际结果 |
| --- | --- |
| 本机后台范围 | 两遍，每遍 747 项测试、230 条共享断言和负向控制；0 失败、0 跳过。排除会干扰前台的 AppKit 测试，不称为完整本机验收 |
| 发布源码完整检查 | [GitHub Mac runner](https://github.com/leo-zhang-source/yukio-desktop-pet/actions/runs/44976752392) 两遍，每遍 Swift 312、工作台 Python 395、发布 Python 28、进度 Python 8、Node 70，共 813 项及 230 条共享断言；全部通过。已下载原始证据并核对产品提交、指纹与实际包 SHA |
| 维护候选完整检查 | [独立维护分支任务](https://github.com/leo-zhang-source/yukio-desktop-pet/actions/runs/44976819805) 两遍，每遍 848 项及 230 条共享断言通过；原始证据已核验。属于候选源码回归，不是候选包或普通用户验收 |
| 实际 ZIP / DMG | 495 个文件/符号链接/执行位条目完全一致，签名有效；与 66.7 相比仅 6 个文件变化，角色素材保持不变 |
| 包内运行环境 | 隔离 HOME 的冻结运行时准备检查通过；离线 Codex/Claude 协议样例验证预览、接收方、发送前复核与仅生成一次。没有使用真实账号或声称真实客户端送达 |
| 公开下载 | 六个附件匿名重新下载，大小与 SHA-256 一致；ZIP 解包后 495 项一致；更新源与 ZIP 签名通过；包内、包外、独立下载的指南字节相同 |
| 桌面实际 App | 已从匿名下载 ZIP 更新到 5.4（66.8）／工作台 0.4.17，495 项与分发清单一致，实际运行进程与安装源码一致。仅后台重启一次；原设置保持，66.7 完整备份保留 |

[机器可读摘要](preview5-validation.json)包含本轮包 SHA、来源和真实覆盖范围。完整原始证据与回退包留在本机 `~/.codex/backups/yukio-preview5-publish-20261121/`，不进入公共附件，不作为 App 的运行依赖。

## GitHub 与下载

[Preview 5 发布页](https://github.com/leo-zhang-source/yukio-desktop-pet/releases/tag/v5.4-preview.5)提供 DMG、ZIP、SHA256SUMS.txt、签名 preview.xml、mac-guide.html 和 release-manifest.json。保留 prerelease，稳定版 latest 仍为 5.3。发布源与 `main` 使用同一签名字节；不修改稳定更新源。

| 包 | 字节数 | SHA-256 |
| --- | ---: | --- |
| `Yukio-5.4-preview.5-macOS-arm64.zip` | 76,974,844 | `31d3ebb40804ea0e30463abbd8b185faf1dccdfbc55cb176054995d4e1c705e3` |
| `Yukio-5.4-preview.5-macOS-arm64.dmg` | 77,379,100 | `9ff8e6e79db7d60fdf42c3da8e642b8141a1f18e6e3c9b91f7d6fc0c92a30607` |

完整维护线保存在 `codex/stage5-maintenance`；发布线从 `codex/remediation-checks/preview5` 按 GitHub 强制检查门槛同步 `main`。没有绕过分支保护、强推、修改旧标签或把候选整包混入当前 App。历史本地小提交与原桌面目录的未核实改动保留；此次只上传审查后的汇总树。新文档中的私人目录使用通用写法，真实聊天、凭据和备份未上传。

源码归档直接写入私有 NAS，并完成远端及流式回读 SHA-256 校验；精确路径在本机证据中。本轮没有删除本地原件。旧包回退只替换 App，不能用旧数据库覆盖新增记录。

## 仍未完成

本版真实聊天跳转、前台显示方式切换/原生全屏、独立安装首次使用和真实多客户端完整矩阵待验。GitHub 上另一台 Mac 的源码测试不替代实际安装包验收。包未 Apple 公证；macOS 13 真机、Intel 与完整自动升级路径不在本轮通过范围。Windows、云端 Cowork 按用户决定暂缓。
