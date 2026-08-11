# AstrBot Multica 桥接插件

<p align="center">
  <img src="logo.svg" width="96" height="96" alt="Multica Bridge Logo" />
</p>

将 AstrBot QQ 机器人接入 [Multica](https://multica.ai) 平台，实现连接测试、ChatOps 等功能。

---

## 功能

- **连接测试**：一键验证 Multica API 连通性
- **配置热生效**：WebUI 中修改配置后即时生效，无需重载
- **Issue 创建**：支持通过 `/multica issue create` 在聊天中直接新建 Issue
- **工作区管理**：支持通过 `/multica workspace` 列出、切换、创建工作区
- **Token 安全**：API 返回配置时自动脱敏敏感字段，防止误保存覆盖
- **会话过滤**：支持群聊/私聊的黑白名单模式，精准控制插件生效范围
- **命令交互**：支持 `/multica` 系列指令，在聊天中直接操作

---

## 安装

### 方式一：AstrBot WebUI 插件市场

1. 打开 AstrBot WebUI → 插件管理
2. 添加插件仓库：`https://github.com/Eason4869/astrbot_plugin_multica_bridge`
3. 点击安装

### 方式二：手动安装

```bash
cd AstrBot/data/plugins
git clone https://github.com/Eason4869/astrbot_plugin_multica_bridge.git
```

---

## 配置

所有配置项均可在 **AstrBot WebUI → 插件 → Multica桥接 → 设置** 页面中修改，修改后自动保存热生效。

### 连接配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enabled` | bool | `true` | 启用/停用插件 |
| `api_url` | str | `https://multica.ai` | Multica API 基地址 |
| `token` | str | — | Multica API 认证 Token |
| `workspace_id` | str | — | Multica 工作区 UUID（可选，留空自动获取） |
| `project_id` | str | — | Multica 项目 UUID（可选） |

### 会话过滤

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `group_chat_mode` | str | `blacklist` | 群聊过滤模式：`blacklist` / `whitelist` / `disabled` |
| `group_chat_list` | list | `[]` | 群聊 ID 列表（根据模式排除或允许） |
| `private_chat_mode` | str | `blacklist` | 私聊过滤模式：`blacklist` / `whitelist` / `disabled` |
| `private_chat_list` | list | `[]` | 用户 ID 列表（根据模式排除或允许） |

---

## 如何获取 Multica API 地址、 Token 和 UUID

### 1. 获取 API 地址

1. Multica Cloud模式（推荐）：一般为 `https://multica.ai`
2. 自托管模式：一般为你的 Multica 服务器地址（未经测试验证）

### 2. 获取认证 Token

1. 登录 Multica Web 控制台
2. 进入 **设置 → API 密钥**（或 **Settings → API Keys**）
3. 点击 **创建密钥**，输入名称（如 `AstrBot Bridge`）
4. 复制生成的 Token，填入本插件的认证 Token 配置项

### 3. 获取工作区及issue UUID（可选）

插件会自动获取工作区 ID，**一般无需手动填写**。如果你需要手动指定，可在 Multica Web 控制台的工作区设置中查看 UUID。


**1. Multica Web 界面（浏览器）**

在 Web 界面的聊天输入框中直接输入命令即可，无需额外安装任何工具。

**获取工作区 UUID**

```bash
# 查看当前工作区完整信息（含 UUID、名称、描述、仓库等）
multica workspace get --output json

# 查看所有工作区列表（表格形式，UUID 默认截断）
multica workspace list

# 查看所有工作区列表 + 完整 UUID
multica workspace list --full-id
```

JSON 输出中的 `id` 字段即为完整 UUID。

**获取 Issue UUID**

```bash
# 查看单个 Issue 详情（含完整 UUID）
multica issue get <issue-id> --output json
# 示例：multica issue get WS-34 --output json

# 查看所有 Issue 列表（表格形式，UUID 默认截断）
multica issue list

# 查看所有 Issue 列表 + 完整 UUID
multica issue list --full-id
```

`<issue-id>` 可以是 Issue Key（如 `WS-34`）、完整 UUID，或 UUID 前缀（≥4 位十六进制）。

**参数说明**

|参数|作用|适用场景|
|-|-|-|
|`--output json`|输出结构化 JSON，`id` 字段天然为完整 UUID|脚本处理、自动化、`jq` 解析|
|`--full-id`|表格模式下展开 UUID 列为完整值|人眼查看、复制粘贴|



**2. Multica CLI（本地终端）**

适用于 Windows / macOS / Linux 本地终端，需先安装并登录。

**安装与登录**

```bash
# 安装 Multica CLI（具体安装方式参考官方文档）
# 本机安装路径：C:\Users\eason\.multica\bin\multica.exe（已加入用户 PATH）

# 登录
multica login
```

**获取工作区 UUID**

```bash
# 查看当前工作区完整信息
multica workspace get --output json

# 指定工作区（支持 UUID / Slug / Short ID）
multica workspace get <workspace-id> --output json
# 示例：multica workspace get d79e9419 --output json
# 示例：multica workspace get eason-service --output json

# 列出所有工作区
multica workspace list --output json
multica workspace list --full-id
```

**获取 Issue UUID**

```bash
# 查看单个 Issue
multica issue get <issue-id> --output json
# 示例：multica issue get WS-34 --output json

# 查询并筛选 Issue
multica issue list --output json
multica issue list --full-id
multica issue list --status in\\\_review --full-id
multica issue list --assignee "agent:AstrBot-运维" --output json
```

**CLI 特有优势**

* 支持管道和脚本：`multica issue list --output json | jq '.\\\[].id'`
* 可批量筛选（按状态、负责人、优先级等）
* 可集成到自动化工作流



**快速对照**

|操作|Web 界面|CLI 本地终端|
|-|-|-|
|当前工作区 UUID|`multica workspace get --output json`|同左|
|所有工作区 UUID|`multica workspace list --full-id`|同左|
|单个 Issue UUID|`multica issue get <id> --output json`|同左|
|所有 Issue UUID|`multica issue list --full-id`|同左|
|管道/脚本处理|不支持|支持 `jq` 等|
|登录方式|浏览器已登录|需 `multica login`|

> \\\*\\\*核心命令完全一致\\\*\\\*——Web 界面和 CLI 使用相同的 `multica` 命令语法，区别仅在于运行环境和后续处理能力。






> 更多细节请参考 Multica 官方文档：
> - [快速上手](https://multica.ai/docs/zh/cloud-quickstart)
> - [认证与令牌](https://multica.ai/docs/zh/auth-tokens)

---

## 指令

在任意允许的群聊或私聊中发送以下命令：

| 指令 | 说明 |
|------|------|
| `/multica help` | 显示帮助信息 |
| `/multica status` | 检查 Multica 连接状态 |
| `/multica issue create <标题> [--desc 描述]` | 通过 API 新建 Issue（不依赖本机 CLI） |
| `/multica workspace list` | 列出当前 Token 可访问的所有工作区 |
| `/multica workspace select <id|slug>` | 切换当前工作区（持久化到插件 config.json，重启后仍生效） |
| `/multica workspace create <名称> [--slug slug] [--desc 描述]` | 创建工作区（slug 缺省时按名称自动生成） |

> 提示：`/multica issue create` 直接调用 Multica HTTP API 创建 Issue，
> 不依赖本机是否安装 `multica` CLI、也不要求 CLI 加入 PATH，
> 可避免“本机未安装 multica”这类误报。

指令受会话过滤配置（黑白名单）控制。

---

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/plug/astrbot_plugin_multica_bridge/config` | 获取当前配置（token 脱敏） |
| POST | `/api/plug/astrbot_plugin_multica_bridge/actions/save_config` | 保存配置 |
| POST | `/api/plug/astrbot_plugin_multica_bridge/actions/test_connection` | 测试连接 |

---

## 开发

```bash
# 克隆仓库
git clone https://github.com/Eason4869/astrbot_plugin_multica_bridge.git
cd astrbot_plugin_multica_bridge

# 安装到 AstrBot（开发模式）
# 将本目录软链接或复制到 AstrBot/data/plugins/
```

---

## 更新日志

详见 [CHANGELOG.md](CHANGELOG.md)

---

## 许可证

MIT
