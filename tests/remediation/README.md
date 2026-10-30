# Mac 与工作台的共同检查

本目录只放人工构造的输入、检查程序和缺陷登记。阶段 3 已修复 Mac 的结果关联；Windows 按用户要求暂停。

从仓库根目录运行，需 macOS、Swift 6.1+、Python 3.12+、Node 22+：

```sh
python3 scripts/run-remediation-checks.py --repeat 2 --out /tmp/yukio-checks-unique
```

`--out` 必须是新的目录。解释器、操作系统、源码指纹、数量、耗时和退出码记在 `summary.json`。每遍使用分开的子进程用户目录及临时目录，不继承模型密钥、端点、代理或客户端登录目录。工具查找路径只有指定测试工具及系统工具。系统组件、网络仍共用，不能算独立用户验收。

程序依次运行 Swift、工作台 Python、网页 Node 和共同输入检查，再验证两个故意错误能被识别。每一步有超时；缺报告、数量为零、意外失败、源码途中改变均会使检查失败。首次构建可从项目锁定的公开依赖地址取得 Sparkle。

- `fixtures/codex-results.json`：13 个场景。比较结束、失败、取消的共同投影；不强制开始、思考等展示相同。
- `check_shared.py`：运行工作台生产解析器，读取 Swift 对同一输入的观察值；两端都检查结束投影与事实元数据。当前 13 组样例的 230 项断言全部符合预期。
- `known-issues.json`：逐步骤记录应有值和修前值。只有两者均匹配登记，才列为 `KNOWN_FAIL`；新变化、意外修好和悬空登记都要求复核。
- `resolved-stage2-issues.json`：保留阶段 2 的 11 处修前差异，已经逐项复核消失，不再作为忽略失败的例外。例外清空后仍用临时人工登记验证“过期例外报警”。
- `fixtures/codex_reply_server.py`：仅接收本次测试自己的 Unix socket，拒绝未列出的协议动作。真实聊天不会收到答案。

`activity_end` 只表示结束，不证明成功。`gate_passed: true` 只表示检查基准稳定；已知错误仍然显示为失败，不能称为产品验收通过。真实窗口焦点、中文输入法、安装、更新和用户账号须分别实测。

完整操作与边界见[场景表](../../docs/remediation/ACCEPTANCE-SCENARIOS.md)。GitHub 工作流准备使用 macOS 15 / Xcode 16.4、Python 3.13、Node 22，依据[官方运行器清单](https://github.com/actions/runner-images/blob/main/images/macos/macos-15-arm64-Readme.md)。当前账号暂停阻止云端实测；合并门槛还需按[分支保护说明](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)实际配置和验证。
