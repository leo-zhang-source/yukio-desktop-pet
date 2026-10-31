<div align="center">

# Yukio · 雪绪

> **账号迁移（2026-10-31）：**可恢复的源码与历史发行资料已迁入 `leo-zhang-source`。主分支包含最新 Mac 集成开发成果，不代表发布了新 App。Mac 5.3 是原公开包，5.4 候选尚未完成独立环境验收。[迁移与版本状态](docs/GITHUB-MIGRATION.md) · [开发入口](DEVELOPMENT.md)。

> **当前重点（2026-10-29）：优先完成 Mac 版本。** Windows 开发、适配、打包、实机测试和发布全部暂缓，作为大后期可选事项保留；现有代码与资料保留，待用户明确要求后再恢复。Windows 不阻塞当前 Mac 验收与交付，独立环境测试要求继续适用于 Mac。

> **GitHub 更新节奏：**小改动先在本地积累和验证，阶段性成果或大更新准备完整后集中上传；避免短时间反复推送、修改 PR、发小版本或更新进度页。用户明确要求立即单独处理时按当次要求执行。

### 与 AI 一起开发时，陪在桌面上的伙伴。

**看见 AI 正在做什么，读懂工作进展，在需要时接过决定权。**

<img src="docs/readme/desk.gif" width="192" alt="雪绪阅读、书写、核对工作，最后举起完成牌">

<p>
<a href="https://github.com/leo-zhang-source/yukio-desktop-pet/releases/latest"><img src="https://img.shields.io/github/v/release/leo-zhang-source/yukio-desktop-pet?label=Latest%20release&color=426854" alt="最新公开版本"></a>
<img src="https://img.shields.io/badge/macOS-13%2B-222222?logo=apple&logoColor=white" alt="macOS 13 或更新版本">
<img src="https://img.shields.io/badge/Windows-downloads%20paused-lightgrey" alt="Windows 下载暂时下架">
<img src="https://img.shields.io/badge/Language-English%20%2F%20中文-426854" alt="支持英文与中文界面">
</p>

[English](README.md) · **简体中文**

**[访问官网 · 试玩角色动画](https://leo-zhang-source.github.io/yukio-website/)**

[下载](#下载) · [功能亮点](#功能亮点) · [角色与动画](#角色与动画) · [开始使用](#开始使用)

</div>

Yukio 将 AI 开发过程带到你的桌面：一位会随工作变化而行动的角色，加上一张能读懂进展的工作台。跟随 **Codex、Claude Code 与 DeepSeek 的 Deep Code CLI**，及时发现需要你参与的时刻，再通过 **Mac 内置活动工作台**了解当前动作、前后背景与工作目的。

平时，看一眼角色就能掌握状态；需要了解更多时，打开工作台，接上思路，再决定下一步。

## 功能亮点

| 陪伴正在进行的工作 | 看清工作背后的进展 |
| --- | --- |
| **把工作状态变成动作。** 十二种动画呈现阅读、书写、测试等活动，桌面一角就能看见进度。 | **用日常语言解释工作。** Mac 工作台说明正在做什么、与前面的工作有什么关系，以及这一步为什么有用。 |
| **优先提醒需要你的事。** 待回答的问题、阻塞错误与完成提醒，优先于普通工作展示。 | **按项目找到聊天。** 展开项目、返回最近聊天、在本机搜索，每段聊天旁都有自己的状态。 |
| **在角色旁回答与决定。** 通过已连接的卡片回答支持的问题，查看完整申请后再决定是否批准。 | **随时接回上下文。** 深入解释当前工作，或按用户要求分段回顾历史，展开原文摘录核对依据。 |

### 多个助手的进展，一眼看见

Yukio 读取三类助手的本机活动记录。你可以指定一个来源，让 **自动**模式同时跟随，也可以固定关注某段聊天。角色上方的简洁气泡显示聊天标题、当前步骤，以及记录中可用的任务清单进度。

多段聊天同时进行时，其余聊天会收进堆叠卡片。展开即可切换关注对象；有可用聊天链接时，还能返回对应的聊天入口。

<p align="center">
<img src="docs/readme/cards-zh.png" width="600" alt="收起与展开的聊天卡片，显示待回答、错误、完成和正在工作的状态">
</p>

### 工作正在发生，也能看懂来龙去脉

在 Mac 上右键点击角色，打开活动工作台。首页围绕三个问题展开：**现在做什么？这意味着什么？为什么要做？** 配置模型后，只要工作台保持打开，说明就能随所选聊天的进展刷新。

<a href="docs/readme/workbench-current.png"><img src="docs/readme/workbench-current.png" width="100%" alt="Mac 活动工作台英文界面：项目侧栏、当前工作、背景与目的"></a>

点击**深入解释**，了解当前工作的具体做法、用途、结果与仍不清楚的部分。点击**之前做了什么**，按每次用户要求浏览简短总结，再展开需要细看的段落。配套的原文摘录，让说明有处可查。

<table align="center" width="100%">
<tr>
<th width="50%">深入了解当前工作</th>
<th width="50%">接回之前的思路</th>
</tr>
<tr>
<td><a href="docs/readme/workbench-deep.png"><img src="docs/readme/workbench-deep.png" alt="深入解释：当前改变、用户决定与核对方式"></a></td>
<td><a href="docs/readme/workbench-history.png"><img src="docs/readme/workbench-history.png" alt="历史回顾：按用户要求分段，提供总结与展开入口"></a></td>
</tr>
</table>

<sub>工作台截图为当前英文界面，使用预设演示数据；点击图片可查看大图。界面也支持中文，模型解释需配置兼容服务。</sub>

### 轮到你时，就在身边回应

问题卡把提示和回答框放在角色旁。Mac 上已连接的 Codex 桌面聊天可在后台接收答案，让你保持当前窗口的焦点。发送失败时保留输入，方便重试。批准卡会先展示完整申请，再由你选择是否继续。

完成提醒帮你及时回到已经结束的工作。问题与批准申请会保留到实际处理；仅仅打开聊天，不会自动回答或批准。

回传能力取决于助手来源及连接配置。具体步骤见[连接指南](YukioPlayer/Resources/BACKGROUND-ANSWERS.md)；网页与浏览器插件连接目前属于实验功能。

## 角色与动画

### 两种风格，陪伴同一张桌面

**雪绪 Yukio** 以白发、蓝眼睛与深蓝制服呈现安静的桌边气质。**千夏 Qianxia** 用浅绿头发、粉色配饰与电子元素带来更轻快的色彩。两位角色都拥有十二种工作动画、独立眨眼和专属提起姿势。

<table align="center" width="100%">
<tr>
<th width="50%">Yukio · 雪绪</th>
<th width="50%">Qianxia · 千夏</th>
</tr>
<tr>
<td align="center"><img src="YukioPlayer/Resources/Assets/base/held@2x.png" height="256" alt="雪绪的提起姿势：白发、蓝眼睛与深蓝制服"></td>
<td align="center"><img src="YukioPlayer/Resources/Assets/skins/qianxia/base/held.png" height="256" alt="千夏的提起姿势：浅绿头发、粉色衣袖与蓝色蝴蝶结"></td>
</tr>
<tr>
<td align="center">安静的配色，熟悉的桌边陪伴。</td>
<td align="center">明亮的细节，轻快的工作节奏。</td>
</tr>
</table>

### 十二种状态，各有自己的表达

读文件时翻开书，编辑时拿起笔，查看图片时举起放大镜。测试、浏览网页、等待回答与完成工作，都有对应的动作和道具。

<img src="docs/readme/states-zh.png" width="100%" alt="雪绪十二种状态：思考、读文件、看图片、写文件、运行测试、浏览网页、整理答复、完成、等待回答、其他工作、失败与待机">

### 小动作，让陪伴鲜活起来

笔尖沿着纸面移动，放大镜扫过图片，双手交替敲击键盘；独立眨眼与阅读视线，让每个状态都有细节。提起角色时，她会随拖动轻轻摆动，放下后逐渐恢复平稳。

<p align="center">
<img src="docs/readme/drag.gif" width="236" alt="雪绪被提起后随拖动摆动，释放后逐渐稳定">
</p>

以上预览展示角色动画素材与拖动效果。动画使用已验收的透明图层，协调手部与道具的运动；制作资料见[动画输入与流程](sources/approved-animation-rig/README.md)。

支持 **50%–200%** 大小调整、自由拖动、角色换装和**待机隐身**，让桌面保留合适的留白。界面可切换中英文；真实聊天名称与引用原话保留原文。

## 下载

**Mac 5.3 为恢复的原版下载。** 文件保留原哈希和包内更新地址。旧账号已不可用，目前软件内更新不可用，请通过下方链接手动安装。较新的 5.4 仍是未完成独立验收的开发候选。[更新说明](docs/MANUAL-UPDATES.md)。

| 平台 | 下载 | 提供的体验 |
| --- | --- | --- |
| **Apple 芯片 Mac · macOS 13+** | **[v5.3 DMG](https://github.com/leo-zhang-source/yukio-desktop-pet/releases/download/v5.3/Yukio-5.3-macOS-arm64.dmg)** · [ZIP](https://github.com/leo-zhang-source/yukio-desktop-pet/releases/download/v5.3/Yukio-5.3-macOS-arm64.zip) | 桌面角色 + 内置活动工作台 |
| **Intel Mac** | [v0.4.6 DMG](https://github.com/leo-zhang-source/yukio-desktop-pet/releases/download/v0.4.6/Yukio-0.4.6-macOS.dmg) · [ZIP](https://github.com/leo-zhang-source/yukio-desktop-pet/releases/download/v0.4.6/Yukio-0.4.6-macOS.zip) | 保留的早期桌面角色版本 |
| **Windows** | 暂时下架 | 暂停提供安装包、便携包及更新文件；源码保留 |

内置工作台面向 Apple 芯片 Mac；Intel 下载保留历史 v0.4.6。Windows 下载继续下架，相关工作按用户决定暂缓。[Windows 状态](docs/WINDOWS-DISTRIBUTION.md)。恢复原包不等于重新完成独立环境验收。[全部发行记录和校验文件](https://github.com/leo-zhang-source/yukio-desktop-pet/releases)。

<details>
<summary><b>macOS 首次打开</b></summary>

Mac：打开 DMG，将 `Yukio.app` 拖到**应用程序**后启动。目前采用临时签名，尚未完成 Apple 公证。若系统拦截了你信任的下载，可在首次尝试打开后前往**系统设置 → 隐私与安全性 → 仍要打开**。

</details>

## 开始使用

1. **启动 Yukio。** 在角色设置中选择外观、语言与大小；用**播放演示**快速浏览工作动画。
2. **开始与编程助手协作。** 在助手设置中选择 Codex、Claude Code、Deep Code 或自动；Yukio 会跟随支持的本机活动记录。
3. **在 Mac 打开工作台。** 右键点击角色，选一个项目或最近聊天，查看当前工作；右上角可进入角色设置。
4. **按需连接更多能力。** 按[回答配置指南](YukioPlayer/Resources/BACKGROUND-ANSWERS.md)连接问题卡，按[模型配置指南](docs/activity-workbench-model-configuration.md)启用更丰富的解释。基础活动跟随无需配置解释模型。

## 工作留在眼前，数据有据可循

活动监测与搜索在本机处理。可选的模型解释只将所选聊天的有限摘录发送到已配置的服务；恢复的 5.3 包保留早期本机／内网解释适配器；开发源码增加了可配置的助手／服务接入，独立用户验收仍待完成。请配置你自己可获得的服务，本仓库不提供作者私人服务。关闭工作台后停止发起新的解释请求，已经发出的请求仍可能完成。

解释依据可读取的活动生成，可能不完整或有误；原文依据与上下文缺失提示始终可查。下载包不包含个人连接配置或活动历史。

## 了解项目

[文档](docs/README.md) · [macOS 源码与构建](YukioPlayer/README.zh-CN.md) · [Windows 源码与构建](YukioWin/README.zh-CN.md) · [版本记录](CHANGELOG.md) · [反馈问题](https://github.com/leo-zhang-source/yukio-desktop-pet/issues)

Yukio 由 **Swift / AppKit** 原生 Mac 角色、**Python** Windows 角色，以及 **Python / JavaScript** 活动工作台组成。角色素材、动画输入与播放器源码都在本仓库中。
