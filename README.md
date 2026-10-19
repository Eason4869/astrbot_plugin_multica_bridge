<div align="center">

<img src="https://raw.githubusercontent.com/Eason4869/astrbot_plugin_multica_bridge/v1.0.0/logo.svg" width="88" height="88" alt="Multica Bridge" />

# AstrBot Multica Bridge

**在 QQ 中进入 Multica，连续对话，随时退出。**

![Version](https://img.shields.io/badge/version-1.0.0-3456cf)
![Branch](https://img.shields.io/badge/branch-main-475569)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB)
![AstrBot](https://img.shields.io/badge/AstrBot-%E2%89%A54.27.2-4f8cff)

[开始使用](#开始使用) · [从旧版升级](#从旧版升级) · [工作模式](#工作模式) · [指令](#指令) · [常见问题](#常见问题)

</div>

为 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 连接 [Multica](https://github.com/multica-ai/multica) 的插件。输入 `/multica`，当前聊天进入工作模式，后续文字直接发给 Multica 智能体；输入 `/multica exit`，恢复普通机器人。

```text
你：/multica
【来自 Multica｜工作模式】已进入工作模式……

你：帮我分析这个项目，先给一个实施方案
【来自 Multica｜工作模式】……

你：继续第二个方向
【来自 Multica｜工作模式】……

你：/multica exit
【来自 Multica｜工作模式】已退出工作模式，恢复普通机器人……
```

## 能做什么

| 功能 | 实际行为 |
| --- | --- |
| 连续对话 | 进入后无需重复命令或每次 @，直接向同一个 Multica Chat 追问 |
| 独占工作回复 | 工作消息由桥接接管，其他插件和 AstrBot 默认模型不再处理、回复这些消息 |
| 聊天窗口隔离 | 群 A 开启后全群共用模式与上下文；群 B、私聊 C 仍可正常使用 AstrBot |
| 来源提示 | 每段工作回复、错误提示均带 `【来自 Multica｜工作模式】` |
| 会话管理 | 恢复对话、新建 Chat、选择智能体、停止执行；WebUI 可退出指定窗口 |
| 保留原功能 | Issue、收件箱、工作区、项目管理及普通模式自然语言控制继续可用 |
| 升级保留连接 | 沿用旧配置路径和字段，保留 URL、Token、工作区、项目与访问规则 |

## 开始使用

需要 Python 3.10+、AstrBot 4.27.2+，以及能够访问的 Multica 服务。Multica 部署版本需提供 Chat API，并具备可用的智能体和运行环境；仅连接测试成功不代表智能体已能执行任务。

### 1. 安装正式版

在 AstrBot 插件管理中通过仓库地址安装或更新：`https://github.com/Eason4869/astrbot_plugin_multica_bridge`。默认使用 `main` 分支；固定版本安装包见 [v1.0.0 Release](https://github.com/Eason4869/astrbot_plugin_multica_bridge/releases/tag/v1.0.0)。也可在 AstrBot 插件目录手动安装：

```bash
cd AstrBot/data/plugins
git clone https://github.com/Eason4869/astrbot_plugin_multica_bridge.git
```

已安装的用户请先阅读下方升级说明。安装完成后重载插件或重启 AstrBot。

### 2. 配置连接

进入 **AstrBot WebUI → 插件 → Multica桥接 → 设置**，填写 API 地址与 Token，点击「测试连接」。在 Multica 侧创建可用 API Token；自托管填写自己的服务器地址。

工作区可留空自动解析，也可指定 ID。读取智能体列表并设置默认智能体：只有一个可用智能体时可自动选择；存在多个且未设默认值时，进入命令会返回编号供选择。

本插件使用自己的设置页保存配置，不使用插件管理的通用齿轮配置入口。设置修改后自动保存并热生效，请确认页面显示保存成功。

### 3. 在 QQ 中开始

在允许的群聊或私聊中发送 `/multica`。成功进入后直接发送文字，与 Multica 连续对话。用 `/multica status` 查看状态，用 `/multica exit` 退出。

## 从旧版升级

**直接更新原插件，保留插件数据即可，无需重新输入 URL 和 Token。** 不要卸载并删除数据，不要重命名插件目录或修改插件标识。

配置继续保存在 AstrBot 数据目录下：

```text
plugin_data/astrbot_plugin_multica_bridge/config.json
```

- 初始化只读取旧配置并补充缺失默认值，不会用默认值回写覆盖旧凭据。
- 首次保存前将原文件备份为同目录的 `config.pre-work-mode.json`。
- 设置页 Token 脱敏显示；留空或保留脱敏值都不会清除旧 Token。仅「清除 Token」并确认会清空它。
- 工作模式与 Chat 绑定单独保存于 `work-mode.json`，重载后继续使用。
- 配置文件损坏时保留原文件，请修复或从备份恢复后重载。

建议升级前备份原插件数据。Git 安装可在原插件目录切换并更新 `main` 分支；如存在本地修改，先保存修改再更新。升级后检查设置页并测试连接，然后在一个测试群验证进入、追问和退出。

## 工作模式

### 按聊天窗口隔离

| 窗口 | 操作 | 结果 |
| --- | --- | --- |
| 群 A | 任一有权限成员输入 `/multica` | 群 A 全体成员共享工作模式与同一 Chat |
| 群 B | 未开启 | 继续与 AstrBot、其他插件正常交互 |
| 私聊 C | 未开启 | 继续普通模式，不受群 A 影响 |
| 群 A | 有权限成员输入 `/multica exit` | 整个群 A 恢复普通模式 |

群聊消息附带发送者信息，方便智能体区分发言人；同群上下文仍是共享的。进入权限也控制工作消息发送权限，可在 AstrBot「指令管理」中配置 `multica enter`。

### 退出、停止与新对话

- `/multica exit`：退出当前 QQ 窗口并停止后续回传。**不会取消 Multica 已接收的任务**，结果仍可在 Multica 查看。
- `/multica stop`：请求停止当前执行并清空排队消息，保持工作模式。需要停止后退出时，先 `stop` 再 `exit`。
- `/multica`：重新进入时复用已有 Chat；退出期间产生的回复不会重新推送到 QQ。
- `/multica new`：新建 Chat，保留旧对话在 Multica 中。
- `/multica agent <编号或ID>`：切换智能体并新建 Chat。

### 消息与故障边界

当前支持文字消息。图片、文件、语音会给出提示，不转交其他插件或默认模型处理。连接失败时保持工作模式并提示错误，避免工作指令被普通模型接收；可随时执行退出命令。

消息仍经过 AstrBot 的全局白名单、会话启停、限流与内容安全检查。独占路由针对工作消息，不会关闭其他插件自身的定时或主动推送。若更新 AstrBot 后入口结构不兼容，插件会提示无法启用工作模式。

## WebUI 工作台

<img src="https://raw.githubusercontent.com/Eason4869/astrbot_plugin_multica_bridge/v1.0.0/assets/workbench.png" width="1100" alt="Multica 工作台：连接状态、工作模式开关、智能体与当前工作会话" />

*界面示例，地址、群号与会话均为演示数据。*

- **总览**：显示连接检测结果、路由就绪状态和正在工作的聊天数量。
- **工作模式**：控制转发开关、设置默认智能体、查看会话并退出指定窗口。
- **连接与访问**：配置 URL、Token、工作区、项目，以及群聊／私聊访问规则。
- **指令与高级设置**：查看常用指令，调整普通模式的自然语言控制。

支持浅色／暗色、中英文及手机布局。工作模式开关关闭后暂停转发，已开启窗口仍需 `/multica exit` 或页面退出操作恢复普通模式。

## 配置

| 配置项 | 默认值 | 用途 |
| --- | --- | --- |
| `enabled` | `true` | 桥接总开关 |
| `api_url` | `https://multica.ai` | Multica API 基地址 |
| `token` | 空 | API Token |
| `workspace_id` / `project_id` | 空 | 指定工作区与项目 |
| `work_mode_enabled` | `true` | 是否允许工作模式转发 |
| `default_agent_id` | 空 | 默认智能体 ID |
| `group_chat_mode` / `private_chat_mode` | `blacklist` | `blacklist`、`whitelist` 或 `disabled` |
| `group_chat_list` / `private_chat_list` | `[]` | 对应群号／私聊用户 ID 列表 |
| `nl_enabled` | `true` | 普通模式自然语言控制 |
| `nl_keyword` | `multica` | 普通模式触发关键词 |
| `nl_llm_enabled` | `true` | 普通模式规则未命中时允许模型解析意图 |

工作模式使用当前 Token 所属账号的 Multica 权限。多人共用时，建议设置会话白名单并限制进入权限。更改 URL、Token、工作区或项目后，使用 `/multica new` 建立新的 Chat 绑定。

## 指令

### 连续对话

| 指令 | 用途 |
| --- | --- |
| `/multica` | 进入或恢复当前窗口的工作模式 |
| `/multica exit` | 退出当前窗口，恢复普通机器人 |
| `/multica new` | 开启新 Chat |
| `/multica agent <编号或ID>` | 选择智能体并开启新 Chat |
| `/multica stop` | 请求停止执行并清空排队消息 |
| `/multica status` | 查看模式、绑定与执行状态；无绑定时显示连接信息 |
| `/multica help` | 查看帮助 |

### Issue 与项目管理

| 指令 | 用途 |
| --- | --- |
| `/multica issue create <标题> [选项]` | 新建 Issue |
| `/multica inbox [数量] [open\|done]` | 查看收件箱，默认 10 条 |
| `/multica workspace list` | 列出工作区 |
| `/multica workspace select <id\|slug>` | 切换工作区并保存配置 |
| `/multica workspace create <名称> [--slug …] [--desc …] [--context …]` | 新建工作区 |
| `/multica project list` | 列出项目 |
| `/multica project select <id>` | 切换默认项目并保存配置 |
| `/multica project create <标题> [--desc …]` | 新建项目 |

```text
/multica issue create 修复登录失败 --desc 用户反馈登录超时 --priority 高 --labels 后端,线上
```

Issue 可选参数：`--desc`、`--priority`（紧急／高／中／低或英文）、`--status`、`--assignee`、`--project`、`--due YYYY-MM-DD`、`--labels 标签1,标签2`。这些功能通过 HTTP API 调用，不需要本机安装 Multica CLI。各子指令可在 AstrBot「指令管理」中分别设置权限；创建工作区、项目和切换全局配置建议限管理员。

### 普通模式自然语言控制

未进入工作模式时，可用关键词触发原有管理功能：

```text
multica 建个issue：修复登录失败，优先级高
multica 收件箱 10 open
multica 切换到项目 前端重构
```

规则优先解析；规则未命中时，可由 `nl_llm_enabled` 控制是否调用 AstrBot 模型解析管理意图。此设置只影响普通模式。工作模式文字直接转发给 Multica。

## 常见问题

**连接测试通过，为什么还无法进入？**

请检查当前 Multica 版本是否提供 Chat API、是否存在可用智能体及运行环境，同时检查会话访问规则和 AstrBot 指令权限。

**忘记退出了怎么办？**

每段工作回复都会标记来源。发送 `/multica exit`，或在设置页的当前工作会话中退出指定窗口。

**升级后设置页看起来没变？**

确认已更新到 1.0.0，重载插件并刷新 AstrBot 页面；必要时强制刷新浏览器缓存。不要通过删除插件数据来刷新设置页。

**已经验证了哪些环境？**

本地 Python 3.10 / 3.12 回归、旧配置覆盖升级、AstrBot 4.27.2 / 4.29.1 源码路由集成，以及 Edge 桌面／手机／主题切换验证已通过。尚未进行真实 QQ 和 Multica 服务联调。具体范围与复现方法见[验证记录](https://github.com/Eason4869/astrbot_plugin_multica_bridge/blob/v1.0.0/docs/verification-1.0.0.md)。

## 项目信息

[更新日志](https://github.com/Eason4869/astrbot_plugin_multica_bridge/blob/v1.0.0/CHANGELOG.md) · [问题反馈](https://github.com/Eason4869/astrbot_plugin_multica_bridge/issues) · [Multica](https://github.com/multica-ai/multica) · [AstrBot](https://github.com/AstrBotDevs/AstrBot) · [MIT License](https://github.com/Eason4869/astrbot_plugin_multica_bridge/blob/v1.0.0/LICENSE)
