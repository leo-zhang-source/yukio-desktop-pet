# 从同一份源码构建完整 Mac 候选包

这是阶段 4 的正式候选构建入口。输出完整 App、供更新测试的 ZIP、拖入 Applications 的 DMG、来源清单及文件校验值。它不安装、不发布，也不自动宣称独立用户验收通过。当前只构建 Apple Silicon Mac；Windows 暂缓，Intel Mac 尚未在本入口验收。

本轮两次构建、实际包检查、恢复结果与尚未通过的验收见 [阶段 4 交付记录](STAGE4-DELIVERY.md)。

## 开发者准备

需要 Apple Silicon Mac、Xcode Command Line Tools、Python 3.12 或更新版本作为启动工具、互联网连接，以及至少 3 GiB 可用空间。普通使用者运行构建好的 App，无需另装 Python、Swift 或这些打包工具。大体积输出应选择足够容量的磁盘，不能把某位作者的 NAS 当成其他用户的运行条件。

版本和依赖集中在 [macos-release.json](../../scripts/macos-release.json)、[Mac 构建依赖](../../scripts/macos-build-requirements.txt) 和 [Swift 依赖锁](../../YukioPlayer/Package.resolved)。当前是 5.4 (41) 候选，工作台 0.4.3；不是已发布版本。

构建会从 [Astral 的公开 Python 发行](https://github.com/astral-sh/python-build-standalone/releases/tag/20260901) 取得固定的 Python 3.12.14，并校验归档哈希。每轮重新展开运行环境、建立独立依赖环境；Python 构建依赖固定版本与 wheel 哈希，Sparkle 固定为 2.10.0。不会从 Applications、Desktop 或作者已安装的 App 提取二进制，也不读取用户聊天、模型配置和账号。

## 执行

先审查并提交本次构建所需改动，再在项目根目录执行。将占位的提交号换成完整 Git 提交号；输出目录必须尚不存在，并位于源码目录之外。

```sh
python3 scripts/build-macos.py --revision <完整提交号> \
  --out <新建候选目录> --cache <公开依赖下载缓存目录>
```

入口脚本本身必须与所选提交一致。工作区其他未提交内容会记录为“排除”，不会混入构建；因此不要用这个命令验证尚未提交的代码。程序从提交导出干净源码，重新编译播放器、冻结工作台服务并组装两套皮肤、语言、回答集成、Sparkle 更新框架和许可说明。

动画原图与图集保持字节不变。现有共享分页工具按源图集生成无损小页并逐页重新解码核对；虽然该工具位于 `YukioWin`，Mac 也使用这些分页，此处不构建或验证 Windows。

## 如何判断构建结果

`build.json` 记录提交、来源、资源、包内文件、工具和签名范围。`source-files.json` 保存本轮源码指纹，`native-dependencies.json` 检查包内二进制不依赖作者目录、最低系统要求不高于 macOS 13。`SHA256SUMS.txt` 对应 ZIP 与 DMG，`logs/` 保留各步骤输出。失败保留现场与 `failure.json`，不复用失败目录覆盖重跑。

再次从相同提交构建到另一个新目录，应比较两份 `build.json` 的 `inputs` 和原始资源；签名、时间信息可能令整个压缩包哈希不同，不能以压缩包逐字节相同作为唯一判据。验证恢复时也检查可执行权限和框架符号链接。

目前输出采用临时签名，清单固定标注 `public_release_ready=false`。正式签名、公证、签名更新源和实际下载后的首次启动必须另行验收。[Sparkle 官方说明](https://sparkle-project.org/documentation/)区分应用签名、公证、更新归档签名和更新列表签名；这里继续启用已有的归档与列表验证，不以关闭验证或系统保护来通过测试。

先在独立 Mac 系统中从实际候选包检查安装、首次启动、用户自己的助手配置、工作台、输入和更新。现有用户升级测试使用真实旧包的副本、独立配置和临时测试签名，不读取正式更新私钥、不替换现用 App。原偶发输入故障、未覆盖的真实输入法以及未验收助手仍分别记录，不能用构建成功代替功能验收。

## 旧入口

`YukioPlayer/scripts/build-app.sh` 是播放器开发包；`package-release.sh` 是历史播放器发布入口；`tools/activity-workbench/build_macos.py` 是独立工作台组件；`build_integrated_macos.py` 是需要显式旧包输入的历史拼装工具。它们为历史复现保留，不能单独代表完整新版本交付。本页入口直接从提交构建，不使用旧 App 作为资源或运行环境来源。
