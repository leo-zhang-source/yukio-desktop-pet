# 使用自己的 Agent 解释工作

工作台 0.4.0 的默认来源为本机 Agent。用户在首页开启后，自动解释所选聊天，三分钟内不重复调度新活动；深入解释和分段回顾仍按需生成。首次未开启时不调用账号。停用、关闭页面和更换聊天仍沿用原有范围限制。选择保存在用户数据目录的 `explanation-provider.json`，不包含密钥或摘录，不随包分发。

- 自动：优先选当前聊天对应的 Codex / Claude Code；未安装时选择另一已安装客户端。Deep Code 聊天也可由已安装的 Codex / Claude Code 解释。
- 指定 Codex 或 Claude Code：只用选定客户端。调用错误不换另一个服务，也不回到千问。
- 自选内网模型：沿用本机 `lan-model.json`。旧授权不会自动授予 Agent。默认模式不依赖该旧文件是否有效。

调用复用自己的登录和账号额度。Claude 需要 Claude Code，而普通网页和普通 Claude 桌面聊天本身没有此入口。Codex 支持 CLI 和 Mac App 内置 CLI；Windows 识别原生程序及 npm 的 JS 入口。Finder/开始菜单缺少 PATH 时会搜索常用安装位置；非标准路径可用本机环境变量 `YUKIO_CODEX_PATH` / `YUKIO_CLAUDE_PATH` 指定程序。Windows npm 入口直接调用 Node，不通过 cmd 拼接命令。

Codex 使用 `exec`、临时会话、只读权限、结构化输出和隔离配置；保留已选模型、模型服务及相关认证方式，不加载用户工具接入。自定义 HTTP 凭据放入仅该子进程的环境变量，不进入命令参数。Claude 使用 `--print`、`--safe-mode`、空工具列表、空 MCP 配置、无会话持久化和结构化输出，继续使用订阅登录；没有使用会跳过订阅登录的 bare 模式。不续写、恢复或发消息给正在工作的聊天。

需客户端支持上述参数；旧版返回升级提示。源码运行普通配置支持 Python 3.9+，Codex 自定义服务/命名 profile 需要 Python 3.11+；Mac 包内置 Python 3.12。超时为 90 秒，限制输出大小并结束本次解释进程树。登录失效、额度不足、缺失客户端、参数不支持、错误格式和错误引用均保留原记录。格式与引用检查不能证明所有解释语义正确。已经提交给服务端的推理不保证能撤回。

本轮验证：248 项 Python 检查（Python 3.12，含两种 CLI 子进程协议、默认选择、Unicode/空格路径、Windows npm 参数适配、首页/深入/回顾、异常回退、超时/超量、服务切换及同源保护）；31 项页面与语言检查通过。后续打包核验另见交付目录中的 verification.json。

真实外部调用：Codex CLI 0.142.3 能读取用户的实际模型选择，但所选模型不受该 CLI 的当前登录支持；未确认成功生成。Claude Code 2.1.195 返回未登录；已确认登录提示，未确认真实生成。不能把协议模拟通过说成两种服务的真实生成都已通过。当前没有可用 Windows 虚拟机，Windows 原生启动、进程树终止、账号登录和实际说明仍未验证。

参数依据：[Claude CLI](https://code.claude.com/docs/en/cli-reference)、[Claude 非交互调用](https://code.claude.com/docs/en/headless)，以及本机 Codex `exec --help` 和配置参考。调用的客户端最终使用自身服务设置；本功能不提供共享账号或开发者内网代理。
