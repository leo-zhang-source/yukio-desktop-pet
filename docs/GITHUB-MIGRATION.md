# GitHub 账号迁移 / Account migration

2026-10-31。目标仓库为 [leo-zhang-source/yukio-desktop-pet](https://github.com/leo-zhang-source/yukio-desktop-pet)，官网为 [Yukio](https://leo-zhang-source.github.io/yukio-website/)。已在新账号恢复可核验的源码、分支、标签、文档和历史发行原件；迁移本身不是新 App 发布。

本次完成 91 条正常分支／标签、29 条历史发行记录和 125 个原始附件的上传与核对，附件合计 5,713,977,679 字节。官网已更新至新账号源码和下载入口；Apple 芯片 5.3 ZIP／DMG、Intel 历史 0.4.6 DMG 均通过匿名完整下载与 SHA-256 校验，官网直下载包也与原件一致。未找到的两个旧附件及其他不可恢复内容见下文。

## 版本与验收

| 内容 | 状态 |
| --- | --- |
| 旧公开主线 | `d80ac4afdcdb30a4f908cebbf2ede11dbfd68277`；历史保留 |
| 最新集成源码 | `8d248f984f18d8483a8b433865a936ab0c61f391`，本次合并旧公开主线及已审查的 Mac 优先约定；主分支包含开发成果 |
| 公开下载 | Mac 5.3 (36) 原始包；ZIP SHA-256 为 `9f674e169273521b0033f0daff19a0af0ebdf0151ea45da702bdce7fd129c700` |
| 作者当前安装 | 5.3.2 (38)，源码 `be9aa07fd5afdd0b4f212102d7b331792da28ce5`；本次未替换 |
| 最新候选 | 5.4 (41)，工作台 0.4.3，源码 `8d2deb2f1752319e6cf5044d8eadd0cb8e74d8bc`；`public_release_ready=false` |
| Windows | 按用户决定暂缓；源码与历史保留，下载及自动发布继续暂停 |

5.4 已补充独立 Mac 基础界面测试证据，但干净首次安装、真实服务与完整功能验收尚未完成，详情页接收方说明仍有已登记问题，签名／公证和公开更新源也待完成。详见 [阶段 4 交付记录](remediation/STAGE4-DELIVERY.md)、[本机界面记录](remediation/STAGE4-GUI-20261030.md)与[10 月 31 日独立 Mac 补充记录](remediation/STAGE4-INDEPENDENT-20261031.md)。此前本机 585 项回归结果属于原记录，不是本次迁移重新执行的验收，也不能代替独立环境验收。

## 历史发行与更新

保存的 29 条旧发行记录中，Windows 下架后保留的 127 个附件已找回并逐个核验 125 个。`v0.2.0/Yukio-0.2.0-macOS.zip` 与 `v0.2.0/SHA256SUMS-v0.2.0.txt` 尚未找到原件，不以重建文件冒充。发行说明增加迁移注记，原标签和文件哈希保持不变；GitHub 新的创建／发布时间不是旧版本的原始发行时间。

原始安装包、签名更新列表与历史清单保留旧账号地址。旧账号不可用，因此原已安装 App 的软件内更新目前不可用。请使用[新账号下载](https://github.com/leo-zhang-source/yukio-desktop-pet/releases/tag/v5.3)手动安装；保留的 `appcast.xml` 是历史原件，不能当作已恢复的更新服务。迁移没有重新签名历史文件，也没有把开发构建入口的旧更新地址直接改指尚未验证的新服务。下一次发行必须一并验证正式更新源、签名、下载、独立用户安装及桌面运行版本。

## 恢复范围

仅按明确映射恢复正常分支和标签，不上传内部恢复树、stash、私密快照或未审查的工作区生成物。相冲突的本地分支与旧远端分支另存恢复分支，保留原提交身份。作者工作区的无关改动和完整私有备份另存。

Git 仓库不包含 Issue／PR 对话、评审、stars、关注关系和完整服务端设置。旧账号无法提供可用清单，没有备份的内容仍不可恢复；不能将本次称为旧账号全部内容恢复。历史文档中的旧账号、Actions 记录、构建路径与测试结果保留原证据含义，不虚构新链接或新验收结论。

## English

**Account migration (2026-10-31):** recoverable source and historical releases have been restored under `leo-zhang-source`. This main branch includes the latest integrated Mac development work; it is not a new app release. Mac 5.3 is the original public package. The 5.4 candidate has not completed independent acceptance. [Developer entry](../DEVELOPMENT.md).

Original package hashes, tags and historical evidence are retained. The old embedded update endpoint is unavailable, so use manual downloads until a new signed update and independently accepted build are delivered. Windows distribution remains deferred. Missing old assets and unbacked GitHub discussions/settings cannot be reconstructed from Git history.
