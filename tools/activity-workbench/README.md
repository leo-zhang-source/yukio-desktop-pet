# 雪绪活动工作台 0.3.0 · Mac 试用版

第8、9步按Mac工程验收与预览交付范围收尾。Windows所有后续测试由用户移为之后的可选任务，不代表Windows新版已验收。

## 直接使用

下载[Mac安装包与说明](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/activity-workbench-v0.3.0)，解压后打开“雪绪活动工作台.app”。已内置运行环境；Apple芯片，构建目标macOS13+，其他系统实机结论见限制。工作台与原桌宠分开，不替换原有桌宠。

打开后选择聊天，下方是内容、解释、原因。上方“让千问解释这段聊天”会显示发送前预览，并说明结果直接出现在本页三处；默认没有发送。可选只解释一次或在本页持续解释最多2小时，切换聊天、记录入口或关页停止，旧同意不会自动延续。

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

同一聊天换文件后只在客户端、聊天编号、助手与分支身份唯一对应时跟进，不按名称猜测，不合并工具结果。旧入口仍在记录详情保留。新入口使旧模型说明和授权清空。

[版本说明](../../docs/releases/activity-workbench-0.3.0.md)与[本轮核验](../../docs/validation/activity-mac-0.3.0/README.md)区分完成、测试与未验证。Windows旧构建入口保留作后续开发参考，不属于本次Mac发布。
