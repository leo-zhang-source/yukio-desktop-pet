# 资料去向与恢复

2026-11-07。这里是维护环境的地图，不是产品对普通用户的路径要求。

| 类别 | 路径/权威来源 | 可否重建、保留与恢复 |
| --- | --- | --- |
| 当前源码与正式素材 | 当前 Git 分支；`YukioPlayer/Resources`；`sources/approved-animation-rig` | 素材是正式输入，不作为缓存清理。源码按本地提交恢复；原图/蒙版/参数保持来源哈希 |
| 公开工作台页面 | `tools/activity-workbench/dist` | 属于实际产品输入，不能当普通构建缓存删除。本轮仅接收方说明及新增对应译文发生有意变化 |
| 历史整改 | 本机 `yukio-remediation` 工作树，原 `codex/remediation-baseline` | 保留候选及已有 29 份未提交资料；不整包替换现用界面 |
| 更早资料 | 桌面 `yukio-cloud-handoff` | 保留/待核实；不自动清理、覆盖或构建 |
| 可重建物 | `YukioPlayer/.build`、各次构建的 work/venv/source/pages、网页预览缓存 | 输入是固定提交/锁与工具版本；本轮不自动删除既有目录 |
| 本轮私有开发证据 | `~/.codex/backups/yukio-stage5-implementation-20261107/` | 原始失败、日志、起点清单、完整测试、包与恢复演练；创建新目录，失败不覆盖 |
| 仓库内可交接证据 | 本目录 evidence 与 TEST_RESULTS | 合成样例/脱敏摘要及哈希；不放真实聊天、账户、令牌或私人模型地址 |
| 大文件/长期归档 | `nas:/volume1/leo/yukio/maintenance/` 下本次独立目录 | 使用 SSH 别名 nas（1529），执行前核查可达、可写和容量；实传/回读位置与 SHA 记录于结果 |
| 用户现用资料 | 用户各自的 Application Support、偏好、钥匙串、助手配置 | 本轮不迁移/恢复/复制；没有把作者现有资料当作产品输入 |
| SSH/签名/助手密钥 | 使用者本机凭据存储 | 不进入源码、包或项目归档；NAS 私钥不离开本机 |

## 可复现恢复方式

先运行维护手册中的 `maintenance_recovery.py drill`。它用项目实际 SQLite 类创建人工记录，通过 backup API 生成一致快照，之后向当前库追加记录，再只恢复到另一个库。检查保存点、记录顺序、重复回放和新 schema 拒绝；原库及追加记录保持。临时 SQLite 超时保留原件与失败输出。

`maintenance_recovery.py archive --source <明确目录> --out <新目录>` 为显式选择的目录生成归档、SHA 和文件清单，并从归档恢复到新的 roundtrip 目录。比较内容、内部符号链接和执行权限；越界路径、越界链接、错误 SHA、已存在输出会失败。归档不保留 ACL/xattr 或钥匙串能力；正式安装包沿用构建工具的 ZIP/DMG，不使用普通 tar 代替分发包。

NAS 回读先比较传输前后 SHA，再把回读文件交给 `restore_archive` 恢复到新目录核对清单。没有 SHA/清单/回读结果，只能叫“复制”，不能叫“恢复演练通过”。应用回退与数据库回退分开；旧程序不能读新 schema 时，保留当前库和新增记录，单独计划迁移，不覆盖成旧库。

实际合成归档：`nas:/volume1/leo/yukio/maintenance/stage5-20261107/recovery-run2/evidence.tar.gz`，参见 [回读实测](evidence/nas-recovery-20261107.json)。原件和第一次 SFTP 失败记录保留。

最终包/证据归档：`nas:/volume1/leo/yukio/maintenance/stage5-20261107/candidate-57-evidence/evidence.tar.gz`。46 文件、153432295 字节，SHA `d71375bd9cb12bd0c348fc0718dfa8c4da5ad8e13e11e56eae938b8730441c8d`；回读清单一致，见 [实际记录](evidence/nas-handoff-20261107.json)。不是用户真实数据库备份。
