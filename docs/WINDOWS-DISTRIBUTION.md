# Windows distribution / Windows 发布状态

**2026-10-27: Windows downloads are temporarily withdrawn from GitHub.**

Windows Setup installers, standalone executables, portable ZIPs, update packages and update feeds are unavailable across current and historical releases. Downloadable Windows build artifacts are also withdrawn. macOS downloads and its signed update feed remain available. Windows source and historical test reports remain in the repository for reference and development. No resumption date has been announced.

**2026-10-27：Windows 版本暂时从 GitHub 下架。**

当前和历史发布中的 Windows 安装程序、独立 EXE、便携 ZIP、完整更新包与更新索引暂停提供；可下载的 Windows 构建包一并下架。macOS 下载及其签名更新列表继续可用。Windows 源码、历史测试报告保留，恢复时间另行公布。

## Release maintenance

- Do not carry Windows assets forward into a new Mac release while this pause is in effect.
- The Windows build/publish and public-download verification workflows are disabled in GitHub. Their source also requires the repository variable `YUKIO_WINDOWS_DISTRIBUTION` to equal `enabled` before running.
- Cross-platform development tests can continue, but Windows binary artifacts must not be uploaded while distribution is paused.
- Removed downloads and original GitHub metadata are retained in a private, SHA-256-verified backup for recovery. Historical checksum lists and validation manifests document their original releases; they do not indicate that Windows downloads are still available.
- Resume only after an explicit decision, fresh Windows validation, coherent release files and documentation, and re-enabling the distribution variable and relevant workflows.

This withdrawal changes distribution availability only. It does not remove an already installed Windows app or its local settings and chats.
