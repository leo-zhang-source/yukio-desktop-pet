# Preview 3 发行前依赖复核

2026-11-11，执行者自审。按照维护台账的 `DEP-native-runtime` 要求检查固定运行时；这不是穷尽的原生库安全认证，也不恢复暂停的独立验收。

## 决定与依据

原包使用 CPython 3.12.14。官方 [3.12.15](https://www.python.org/downloads/release/python-31215/) 修复 SSL、归档提取等问题；[3.12.16](https://www.python.org/downloads/release/python-31216/) 继续修复证书信任、Expat、归档与临时目录问题。仅靠构建依赖的 pip-audit 不能覆盖这些运行时更新，因此本次固定升级到 3.12.16。

选用 [Astral 20261026 发行](https://github.com/astral-sh/python-build-standalone/releases/tag/20261026)的 `cpython-3.12.16+20261026-aarch64-apple-darwin-install_only.tar.gz`，25,172,086 字节，GitHub 发行资产摘要 `fbf4afef53c2a6b72bb741bc06d5671a9dfaf87bd84e5aa73ac9b3d0d589f14e`。构建入口再次校验下载哈希和解释器实际版本。保留原 PSF 及捆绑许可，现有 Python wheel 锁不变。

[20261110 发行](https://github.com/astral-sh/python-build-standalone/releases/tag/20261110)仍为同一 Python 补丁版本，另含 zlib、libedit、Expat 等升级。本次先固定含所需 CPython 修复的 20261026 归档，不因为“最新”自动扩大依赖变更。此决定仍需实际包验证，不将官方版本号当作应用兼容结论。

Sparkle 保持 2.10.0。[官方安全公告](https://github.com/sparkle-project/Sparkle/security/advisories)列出的五份公告受影响范围截至 2.9.5 或更早；本次查询未见公告将 2.10.0 列为受影响版本，这不等于穷尽安全保证。[2.10.1](https://github.com/sparkle-project/Sparkle/releases/tag/2.10.1)包含 Unicode 安装路径等修复，原台账的真实升级／取消／重启验收仍待完成，因此保留为单独维护项。

## 验证与边界

两遍完整回归、固定 wheel 审计、实际包中的运行时版本／原生依赖检查、隔离资料目录启动和包哈希结果见[本次交付记录](RELEASE-54-PREVIEW3.md)。实际执行后登记结果；未执行项目不能按旧版通过继承。

普通使用者不需安装 Python；不引入维护者的 Homebrew、私有服务或凭据。完整独立首次使用、macOS 13 真机与 Intel 不在本次已验范围。
