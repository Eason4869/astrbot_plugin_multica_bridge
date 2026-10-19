<div align="center">

<img src="https://raw.githubusercontent.com/Eason4869/astrbot_plugin_multica_bridge/dev/logo.svg" width="88" height="88" alt="Multica Bridge" />

# AstrBot Multica Bridge

**在 QQ 中进入 Multica，连续对话，随时退出。**

![Version](https://img.shields.io/badge/version-1.2.1-3456cf)
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
| 聊天窗口隔离 | 仅开启者的文字转发；同群其他成员、其他群和私聊继续正常使用 AstrBot |
| 来源提示 | 每段工作回复、错误提示均带 `【来自 Multica｜工作模式】` |
| 会话管理 | 恢复对话、新建 Chat、选择智能体、停止执行；WebUI 可退出指定窗口 |
| 保留原功能 | Issue创建、Issue列表及兼容管理命令保留；自然语言支持进入模式、查询和 Issue 草稿确认 |
| 升级保留连接 | 沿用旧配置路径和字段，保留 URL、Token、工作区、项目与访问规则 |

## 开始使用

需要 Python 3.10+、AstrBot 4.27.2+，以及能够访问的 Multica 服务。Multica 部署版本需提供 Chat API，并具备可用的智能体和运行环境；仅连接测试成功不代表智能体已能执行任务。

### 1. 安装正式版

在 AstrBot 插件管理中通过仓库地址安装或更新：`https://github.com/Eason4869/astrbot_plugin_multica_bridge`。正式版本使用 `main` 分支，开发更新使用 `dev` 分支。也可从 [Releases](https://github.com/Eason4869/astrbot_plugin_multica_bridge/releases) 下载已发布版本的安装 ZIP 和 SHA256 校验文件，或在 AstrBot 插件目录手动安装：

```bash
cd AstrBot/data/plugins
git clone https://github.com/Eason4869/astrbot_plugin_multica_bridge.git
```

已安装的用户请先阅读下方升级说明。安装完成后重载插件或重启 AstrBot。

### 2. 配置连接

进入 **AstrBot WebUI → 插件 → Multica桥接 → 设置 → 连接与访问**，填写 API 地址与 Token，点击填写区旁的「测试连接」。测试会自动读取当前 Token 可访问的全部工作区，将名称和完整 ID 显示在「默认工作区」下拉框。在 Multica 侧创建可用 API Token；自托管填写自己的服务器地址。

只有一个工作区时可以留空自动解析；存在多个工作区时必须从下拉框明确选择，不会自动选第一项。选择后自动保存，完整 ID 显示在下拉框下方，获取方法见「常见问题」。再读取智能体列表并设置默认智能体：只有一个可用智能体时可自动选择；存在多个且未设默认值时，进入命令会返回编号供选择。

本插件使用自己的设置页保存配置，不使用插件管理的通用齿轮配置入口。设置修改后自动保存并热生效，请确认页面显示保存成功。

### 3. 配置 Multica 放行用户名单

在设置页填写放行的用户 ID 或完整 UMO，每行一项，可以混填；匹配任意一项即放行。名单为空时无人可用。

| 填法 | 作用范围 |
| --- | --- |
| `用户QQ号` | 该用户可在所有群聊和私聊使用 |
| `机器人ID:FriendMessage:用户QQ号` | 仅该用户通过 机器人ID 的私聊可用，群聊不匹配 |
| `机器人ID:GroupMessage:群号` | 放行 机器人ID 所在的该群所有成员使用指令 |

未获放行时回复：`您没有使用Multica的权限，请联系管理员获取使用资格`。指令默认向所有人开放；历史上单独配置的管理员限制仍生效，可在 AstrBot「指令管理」改为所有人。

### 4. 在 QQ 中开始

放行后在群聊或私聊中发送 `/multica`，也可说“进入multica模式”“切换为multica工作”。成功进入后直接发送文字，与 Multica 连续对话。用 `/multica status` 查看状态，用 `/multica exit` 退出。

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

### 按窗口保存，群聊仅开启者转发

| 窗口 | 操作 | 结果 |
| --- | --- | --- |
| 群 A | 任一有权限成员输入 `/multica` | 仅开启者的文字进入该 Chat；其他群友继续使用 AstrBot |
| 群 B | 未开启 | 继续与 AstrBot、其他插件正常交互 |
| 私聊 C | 未开启 | 继续普通模式，不受群 A 影响 |
| 群 A | 开启者输入 `/multica exit` | 结束该工作会话 |

群聊工作消息附带开启者昵称和 QQ 号。只有开启者的消息转发，回复仍在群内可见；其他成员不能接管或退出该会话。开启者退出后，另一人开启将新建 Chat。旧版没有开启者信息的共享会话升级后暂停，请用 `/multica new` 建立新会话。

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

<img src="https://raw.githubusercontent.com/Eason4869/astrbot_plugin_multica_bridge/dev/assets/workbench.png" width="1100" alt="Multica 工作台：连接测试、默认工作区下拉框、智能体与当前工作会话" />

*界面示例，地址、群号与会话均为演示数据。*

- **总览**：显示连接检测结果、路由就绪状态和正在工作的聊天数量。
- **工作模式**：控制转发开关、设置默认智能体、查看会话并退出指定窗口。
- **连接与访问**：配置 URL、Token、工作区、项目，以及统一的 Multica 放行用户名单。
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
| `multica_whitelist` | `[]` | 放行的 UID 或完整 UMO 列表，空列表拒绝所有用户 |
| `nl_enabled` | `true` | 普通模式自然语言控制 |
| `nl_keyword` | `multica` | 普通模式触发关键词 |
| `nl_llm_enabled` | `true` | 普通模式规则未命中时允许模型解析意图 |

工作模式使用当前 Token 所属账号的 Multica 权限。只向可信用户或会话放行。旧群聊/私聊过滤字段不再控制权限；若旧配置明确使用私聊白名单，其条目会在内存中迁为放行名单，其他情况需要重新填写。更改 URL、Token、工作区或项目后，使用 `/multica new` 建立新的 Chat 绑定。

## 指令

### 连续对话

| 指令 | 用途 |
| --- | --- |
| `/multica` | 进入或恢复当前窗口的工作模式 |
| `/multica exit` | 退出当前窗口，恢复普通机器人 |
| `/multica new` | 开启新 Chat |
| `/multica agent [编号或ID]` | 无参数列出智能体；指定后开启新 Chat |
| `/multica stop` | 请求停止执行并清空排队消息 |
| `/multica status` | 查看模式、绑定与执行状态；无绑定时显示连接信息 |
| `/multica help` | 查看帮助 |

### 高级 Issue 与兼容管理命令

| 指令 | 用途 |
| --- | --- |
| `/multica issue create <标题> [选项]` | 新建 Issue |
| `/multica inbox [数量] [open\|done]` | 查看Issue列表，默认 10 条 |
| `/multica workspace list` | 列出工作区 |
| `/multica workspace select <id\|slug>` | 切换工作区并保存配置 |
| `/multica workspace create <名称> [--slug …] [--desc …] [--context …]` | 新建工作区 |
| `/multica project list` | 列出项目 |
| `/multica project select <id>` | 切换默认项目并保存配置 |
| `/multica project create <标题> [--desc …]` | 新建项目 |

```text
/multica issue create 修复登录失败 --desc 用户反馈登录超时 --priority 高 --labels 后端,线上
```

Issue 可选参数：`--desc`、`--priority`（紧急／高／中／低或英文）、`--status`、`--assignee`、`--project`、`--due YYYY-MM-DD`、`--labels 标签1,标签2`。这些功能通过 HTTP API 调用，不需要本机安装 Multica CLI。旧管理命令保留原权限配置；工作区与项目选择全局生效，建议在 WebUI 读取列表并选择。切换工作区清空旧项目，旧 Chat 绑定暂停，需要 `/multica new`。

这里的 **Issue列表** 查询当前工作区的 Issue，不是 Multica 的通知收件箱。可使用 `/multica Issue列表` 或 `/multica issue列表`；原 `/multica inbox` 和中文旧别名继续兼容。

### 普通模式自然语言控制

未进入工作模式时，可用关键词触发原有管理功能：

```text
multica 建个issue：修复登录失败，优先级高
multica Issue列表 10 open
进入multica模式
切换为multica工作
```

规则优先解析，明确进入语句不消耗 AstrBot 模型。可执行意图为进入模式、帮助、状态、Issue列表和创建 Issue。Issue 先显示草稿，120 秒内由本人回复“确认 六位短码”才提交，可回复“取消 六位短码”；重复确认不会重复写入。否定、教学、引用和复合请求不自动执行，项目/工作区的自然语言管理改为设置页指引。

规则无法解析时，由 `nl_llm_enabled` 决定是否调用模型，限时 10 秒且不自动重试。工作模式文字直接转发给 Multica，退出使用 `/multica exit`；说“退出工作模式”不会改变本地模式。

## 常见问题

**有多个工作区时，如何获取工作区 ID 并选择默认工作区？**

工作区 ID 是 Multica 为工作区分配的唯一标识，通常是 UUID，例如 `12345678-1234-1234-1234-123456789abc`。应复制工作区对象的 `id`，不要填项目 ID、智能体 ID、用户 ID 或工作区显示名称。以下方法都只会列出当前 Token 有权限访问的工作区。

**方法一：直接在插件设置页读取并选择（推荐）**

1. 打开 **AstrBot WebUI → 插件 → Multica桥接 → 设置 → 连接与访问**。
2. 填写 Multica API 地址和 Token，确认已启用桥接，等待页面提示「所有更改已保存」。已有 URL / Token 无需重填。
3. 点击 API 地址和 Token 填写区旁的 **测试连接**。连接有效后，插件会自动读取工作区列表，无需先知道工作区 ID。
4. 展开 **默认工作区** 下拉框，按 **工作区名称 · 完整 ID** 找到目标工作区。若有多个且尚未指定，会提示选择；已有有效选择会保留，不会被第一项覆盖。
5. 选中后等待自动保存成功。下拉框下方显示选中工作区的完整 ID，可选中复制；如需重新获取列表，点击 **读取工作区**。
6. 再测试连接，核对显示的工作区名称。需要绑定项目时，在此工作区下点击 **读取项目**，选择对应项目。

只有一个工作区时可以保留「自动使用唯一工作区」；多个工作区时请明确选择。若原 ID 已失效，下拉框会保留原值并提示不可访问，需要重新选一个有效项。

**方法二：在 QQ 中使用保留的管理命令**

先确保自己的 QQ UID 或所在会话 UMO 已加入插件放行名单，且 AstrBot 未禁用相关指令。在机器人聊天中发送：

```text
/multica workspace list
```

返回示例（以下是演示数据，不是你的真实 ID）：

```text
共 2 个工作区：
• 研发工作区（slug: development）
  12345678-1234-1234-1234-123456789abc
• 生产工作区（slug: production）
  87654321-4321-4321-4321-cba987654321
```

每个名称下方的一整行就是工作区 ID。复制目标 ID 后，可发送以下命令切换并自动保存默认工作区：

```text
/multica workspace select 12345678-1234-1234-1234-123456789abc
```

命令也支持完整 slug（例如 `development`），但完整 ID 最明确。列表查询不要求预先选好工作区；不要用 `/multica status` 代替首次列表查询。

**方法三：直接通过 Multica API 查询（备用）**

使用与插件设置相同的 API 基地址和 Token，发送 `GET <API基地址>/api/workspaces`，认证头为 `Authorization: Bearer <Token>`。Windows PowerShell 可使用以下只读命令；将地址替换为自己的地址，Token 在提示时输入：

```powershell
$multicaBaseUrl = "https://你的Multica地址".TrimEnd('/')
$multicaSecureToken = Read-Host "输入 Multica API Token" -AsSecureString
$multicaCredential = [System.Management.Automation.PSCredential]::new("multica", $multicaSecureToken)
$multicaHeaders = @{ Authorization = "Bearer " + $multicaCredential.GetNetworkCredential().Password }
$multicaWorkspaces = Invoke-RestMethod -Method Get -Uri "$multicaBaseUrl/api/workspaces" -Headers $multicaHeaders
$multicaWorkspaces | Select-Object name, slug, id | Format-Table -AutoSize
Remove-Variable multicaHeaders, multicaCredential, multicaSecureToken
```

输出中 `id` 列就是所需的完整工作区 ID；`name` 用来辨认，`slug` 是工作区别名。该查询不需要 `workspace_id`，不会创建或修改工作区。接口实现可参阅 [Multica 官方工作区接口](https://github.com/multica-ai/multica/blob/main/server/internal/handler/workspace.go)。

**读不到列表或切换后不能继续对话？**

- 提示存在多个工作区：表示需要明确选择，不能依赖留空自动发现；新设置页会将「连接成功」与「待选择工作区」分别提示。
- 下拉框暂无选项：先测试连接；也可用「读取工作区」刷新。查询失败不会覆盖已保存的工作区 ID。
- `401`：检查 Token 是否正确或已失效；`403` 或找不到目标工作区：检查 Token 所属账号是否有访问权限、API 地址是否属于正确实例。空列表表示当前 Token 没有可列出的工作区。
- 设置页没有下拉框或按钮仍在顶部：需要安装包含本次界面改动的版本，重载插件并强制刷新页面；旧版也可先用方法二或三获取 ID。
- **默认工作区是插件全局配置，并非按群单独设置。** 切换工作区会清空旧项目，已有 Chat 绑定会暂停；重新选择项目后，在受影响聊天发送 `/multica new` 建立新绑定。工作模式的聊天隔离不等于每个窗口可单独设置默认工作区。

**连接测试通过，为什么还无法进入？**

请检查当前 Multica 版本是否提供 Chat API、是否存在可用智能体及运行环境，同时检查会话访问规则和 AstrBot 指令权限。

**忘记退出了怎么办？**

每段工作回复都会标记来源。发送 `/multica exit`，或在设置页的当前工作会话中退出指定窗口。

**升级后设置页看起来没变？**

确认已安装对应版本，重载插件并刷新 AstrBot 页面；必要时强制刷新浏览器缓存。不要通过删除插件数据来刷新设置页。

**已经验证了哪些环境？**

Python 3.10 / 3.12 各 201 项测试通过，覆盖官方日志接口、旧配置升级、多工作区发现与两个 AstrBot 源码版本；1.2.0 的 Edge 桌面/手机/主题/双语验证继续适用，本次仅修复日志来源。远程检查见 [CI](https://github.com/Eason4869/astrbot_plugin_multica_bridge/actions/workflows/ci.yml)。尚未进行真实 QQ、Multica 和真实模型评测；自动化通过不代表线上联调完成。具体范围见[验证记录](https://github.com/Eason4869/astrbot_plugin_multica_bridge/blob/dev/docs/verification-1.2.1.md)。

## 项目信息

[更新日志](https://github.com/Eason4869/astrbot_plugin_multica_bridge/blob/dev/CHANGELOG.md) · [问题反馈](https://github.com/Eason4869/astrbot_plugin_multica_bridge/issues) · [Multica](https://github.com/multica-ai/multica) · [AstrBot](https://github.com/AstrBotDevs/AstrBot) · [MIT License](https://github.com/Eason4869/astrbot_plugin_multica_bridge/blob/dev/LICENSE)
