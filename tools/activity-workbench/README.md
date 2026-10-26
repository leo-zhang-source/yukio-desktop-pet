英文补齐候选：工作台0.3.8 / Mac雪绪0.4.11。英文模式统一界面、状态、交接和生成说明；聊天名称、项目名称与引用原话保留原文。安装与发布以本轮核验为准。[说明](../../docs/ACTIVITY-ENGLISH-COMPLETENESS.md)。

当前 Mac 内置工作台0.3.7（雪绪0.4.9）：项目在上、最近聊天在下，工作状态只作旁边标识；按系统显示中英文，说明交代背景及用途。旧版发布记录见下文。Windows继续留作之后可选。

> Mac 0.4.8 embeds workbench 0.3.6: system language, Chinese/English explanations, readable context and no raw diagnostic prose. [Details and limits](../../docs/ACTIVITY-LANGUAGE-AND-CONTEXT.md).

> 已随 Mac 雪绪 0.4.7 提供本轮工作台：右键桌宠打开，在顶部右侧进入设置。公开源码、包与桌面安装依据见 [0.4.7 发布记录](../../docs/releases/0.4.7.md)。以下各小版本的本机说明保留作历史。

# 雪绪活动工作台 0.3.5 · 聊天侧栏与分类设置

本机 Mac 集成版已装进桌面 Yukio：右键雪绪打开，顶部右侧进入设置。原独立版继续保留。范围见[接入说明](../../docs/ACTIVITY-PET-INTEGRATION.md)。

本地0.3.5增加按项目展开的聊天侧栏、最近／正在工作／未在工作分类与本机搜索；Mac 内置设置分成外观与显示、聊天与提醒、更多设置。沿用0.3.4的具体对象名称与历史标题；公开下载基础版仍为0.3.0，本轮未发布新版本。第8、9步按Mac工程验收与预览交付范围收尾。Windows所有后续测试由用户移为之后的可选任务，不代表Windows新版已验收。

## 直接使用

下载[Mac安装包与说明](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/activity-workbench-v0.3.0)，解压后打开“雪绪活动工作台.app”。已内置运行环境；Apple芯片，构建目标macOS13+，其他系统实机结论见限制。工作台与原桌宠分开，不替换原有桌宠。

打开后选择聊天，下方是内容、解释、原因。按用户明确设置，打开页面后自动解释所选聊天，页面打开时持续跟进，关掉停止后续发送。原来的“解释一次／持续解释”按钮已移除。新增的“深入解释”只在需要时展开当前工作的做法、前后联系、用途和限制；“之前做了什么”按每次要求分段，每次显示三段千问简短总结，可再展开任一段。两个新入口不改变首页的自动说明。发送范围、接收位置和限制在折叠的“说明与隐私”中查看。持续打开时通过心跳续期；浏览器异常退出后旧授权最多两分钟失效。至少间隔3分钟、没有变化不重复生成，保留调用预算。自动设置只绑定本机已配置的接收位置，不随包分发或继承到新接收位置。

本机说明可以直接使用；模型没有配置时不影响查看记录。Mac数据仍在应用支持目录YukioPlayer/activity-observation，包中不含个人历史、配置、密钥或项目说明。模型配置方式见[解释接口说明](../../docs/activity-workbench-model-configuration.md)；密钥不写入源码。当前接口适配器仅接受无鉴权内网兼容接口，不把占位密钥当安全凭据。

## 从源码运行与检查

```sh
python3 tools/activity-workbench/launcher.py --collect
python3 -m unittest discover -s tools/activity-workbench -p 'test_*.py' -v
node --test tools/activity-workbench/test_glance_ui.cjs
```

发布源码附带core/yukio的最小采集依赖；完整开发仓库也可复用YukioWin中的对应模块。仅使用Python标准库，不依赖桌宠界面。

Mac构建需Apple芯片Mac、Swift命令行工具、Python3.9+及requirements-build-macos.txt。请选择面向目标系统编译的Python；开发电脑的Homebrew环境可能要求更高的macOS。使用隔离环境构建：

```sh
python3 -m venv .build-venv
.build-venv/bin/python -m pip install -r tools/activity-workbench/requirements-build-macos.txt
.build-venv/bin/python tools/activity-workbench/build_macos.py --out build/mac-preview
```

最终构建使用Python3.12.14、PyInstaller6.22.3，Swift目标macOS13。本地临时签名，未完成Apple公证。不得关闭系统安全保护来运行。

## 证据与边界

当前说明只基于可核对的短记录，分别标注记录、助手自述和推测，不读取隐藏思考。来源丢失、改写或对应不清时保留未知。历史元数据保存在本机；短摘录临时读取；仅监听127.0.0.1，保留Host、Origin及同源请求头校验。

同一聊天换文件后只在客户端、聊天编号、助手与分支身份唯一对应时跟进，不按名称猜测，不合并工具结果。唯一匹配的本机项目背景会随同一聊天接续；旧模型说明和发送授权仍清空。单次说明生成后保留在三段位置，后续新活动会明确标为“刚才的说明”，不会冒充最新活动。

[版本说明](../../docs/releases/activity-workbench-0.3.0.md)与[本轮核验](../../docs/validation/activity-mac-0.3.0/README.md)区分完成、测试与未验证。Windows旧构建入口保留作后续开发参考，不属于本次Mac发布。

0.3.1 的当前操作结果由本机依据回执补到“内容”，模型仍须引用当前动作；错误引用、已结束却声称正在做、夸大保证等检查继续保留。三段展示会用对象类别替代技术细节；只有记录明确给出用途时，才称为“封面图”等具体用途。原始短依据默认折叠。详见[本轮修复记录](../../docs/validation/activity-explanation-0.3.1/README.md)。

0.3.2 自动说明的测试与关闭边界见[本轮核验](../../docs/validation/activity-auto-page-0.3.2/README.md)。

0.3.3 的设计、真实试用与限制见[深入说明与分段回顾](../../docs/ACTIVITY-READING.md)。本次只交付本机 Mac App 和桌面安装包，未推送或发布到 GitHub。

0.3.4 区分不同按钮与功能的名称，修复标题丢掉逗号后名称的问题。见[对象名称说明](../../docs/ACTIVITY-OBJECT-NAMES.md)。

0.3.5 的实现、状态判断和本机交付范围见[聊天侧栏与设置](../../docs/ACTIVITY-CHAT-NAVIGATION.md)。
