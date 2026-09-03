<p align="center">
  <img src="logo.svg" width="110" height="110" alt="Multica Bridge Logo" />
</p>

<h1 align="center">AstrBot Multica 桥接插件</h1>

<p align="center">
  <em>✨ AstrBot × Multica ✦ 一键接入 ✦ ChatOps 赋能 ✨</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/AstrBot-Multica%20Bridge-4f8cff" alt="AstrBot Multica Bridge" />
  <img src="https://img.shields.io/badge/Multica-API-8b5cf6" alt="Multica API" />
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="MIT License" />
  <img src="https://img.shields.io/badge/PRs-Welcome-brightgreen" alt="PRs Welcome" />
  <img src="https://img.shields.io/badge/%E8%B5%9E%E5%8A%A9-%E6%89%93%E8%B5%8F%E6%94%AF%E6%8C%81-ff69b4" alt="赞助支持" />
</p>

<p align="center">
  <img src="assets/banner-anime.jpg" width="640" alt="Anime banner" />
</p>

将 AstrBot QQ 机器人接入 [Multica](https://multica.ai) 平台，实现连接测试、ChatOps 等功能。

<p align="center">
  <img src="assets/divider.gif" width="480" alt="数据流动分隔线" />
</p>

---

## ✨ 功能

- **连接测试**：一键验证 Multica API 连通性
- **配置热生效**：WebUI 中修改配置后即时生效，无需重载
- **Issue 创建**：支持通过 `/multica issue create` 在聊天中直接新建 Issue
- **工作区管理**：支持通过 `/multica workspace` 列出、切换、创建工作区
- **项目管理**：支持通过 `/multica project` 列出、切换、创建项目，新建 Issue 默认进入所选项目
- **收件箱同步**：支持通过 `/multica inbox` 在聊天中查看最近 Issue 及进展
- **Token 安全**：API 返回配置时自动脱敏敏感字段，防止误保存覆盖
- **会话过滤**：支持群聊/私聊的黑白名单模式，精准控制插件生效范围
- **命令交互**：支持 `/multica` 系列指令，在聊天中直接操作
- **权限管理**：`/multica` 作为 AstrBot 一等指令，可在「指令管理」中设为仅管理员等

---

## 📦 安装

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

## ⚙️ 配置

所有配置项均可在 **AstrBot WebUI → 插件 → Multica桥接 → 设置** 页面中修改，修改后自动保存热生效。

> 注意：插件**不提供** AstrBot 插件管理页面中的「齿轮」配置入口（`_conf_schema.json`）。
> 齿轮入口的配置由 AstrBot 单独持久化、插件运行时并不读取，修改无法生效；
> 因此统一以上述设置页面为唯一配置入口，避免两套配置互不同步。

### 连接配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enabled` | bool | `true` | 启用/停用插件 |
| `api_url` | str | `https://multica.ai` | Multica API 基地址 |
| `token` | str | — | Multica API 认证 Token |
| `workspace_id` | str | — | Multica 工作区 UUID（可选，留空自动获取） |
| `project_id` | str | — | Multica 项目 UUID（可选，可用 `/multica project select <id>` 切换并持久化） |

### 会话过滤

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `group_chat_mode` | str | `blacklist` | 群聊过滤模式：`blacklist` / `whitelist` / `disabled` |
| `group_chat_list` | list | `[]` | 群聊 ID 列表（根据模式排除或允许） |
| `private_chat_mode` | str | `blacklist` | 私聊过滤模式：`blacklist` / `whitelist` / `disabled` |
| `private_chat_list` | list | `[]` | 用户 ID 列表（根据模式排除或允许） |

---

## 🔑 获取 API 地址、Token 与 UUID

### 1. API 地址

1. Multica Cloud 模式（推荐）：一般为 `https://multica.ai`
2. 自托管模式：一般为你的 Multica 服务器地址

### 2. 认证 Token

1. 登录 Multica Web 控制台
2. 进入 **设置 → API 密钥**（或 **Settings → API Keys**）
3. 点击 **创建密钥**，输入名称（如 `AstrBot Bridge`）
4. 复制生成的 Token，填入插件的「认证 Token」配置项

### 3. 工作区 / 项目 / Issue UUID（一般无需手动填写）

插件会在首次调用时**自动解析当前工作区**的 ID，并可通过 `/multica workspace list`
等在聊天中查看与切换，多数场景下不需要手动获取 UUID。

如确需在平台侧查阅，可用平台自身的查看命令（Web 端或终端语法一致），例如：

- 查看工作区完整信息：`multica workspace get --output json`
- 列出工作区 / Issue：`multica workspace list`、`multica issue list`（可加 `--full-id` 展示完整 UUID）
- 查看单个 Issue 详情：`multica issue get <id> --output json`

JSON 输出中的 `id` 字段即为完整 UUID；而使用聊天指令时，标题 / slug / UUID
都会展示给你，直接复制即可。

> 补充：本插件与 Multica 的交互**全部经由 HTTP API**（不依赖安装本地 CLI、
> 也不要求其加入 PATH），因此无论你使用 Web 端还是终端维护数据，
> 插件都能正确取用工作区 / 项目与 Issue。

更多细节请参考 Multica 官方文档：
- [快速上手](https://multica.ai/docs/zh/cloud-quickstart)
- [认证与令牌](https://multica.ai/docs/zh/auth-tokens)

---

## 💬 指令

在任意允许的群聊或私聊中发送以下命令：

| 指令 | 说明 |
|------|------|
| `/multica help` | 显示帮助信息 |
| `/multica status` | 检查 Multica 连接状态 |
| `/multica issue create <标题> [--desc 描述]` | 通过 API 新建 Issue（不依赖本机 CLI） |
| `/multica workspace list` | 列出当前 Token 可访问的所有工作区 |
| `/multica workspace select <id\|slug>` | 切换当前工作区（持久化到插件 config.json，重启后仍生效） |
| `/multica workspace create <名称> [--slug slug] [--desc 描述] [--context 背景]` | 创建工作区（slug 缺省时按名称自动生成） |
| `/multica project list` | 列出当前工作区下的所有项目（标题、id） |
| `/multica project select <id>` | 切换当前项目（持久化到插件 config.json，重启后仍生效；新建 Issue 默认进入所选项目） |
| `/multica project create <标题> [--desc 描述]` | 创建项目（title 必填，可选描述） |
| `/multica inbox [数量] [open\|done]` | 查看收件箱：最近 Issue（默认 10 条，按更新时间倒序）；`open` 只看未完成，`done` 只看已完成/已取消 |

> 提示：`/multica issue create` 直接调用 Multica HTTP API 创建 Issue，
> 不依赖本机是否安装 Multica CLI、也不要求 CLI 加入 PATH，
> 可避免“本机未安装 Multica”这类误报。

> 提示：`/multica inbox` 同样直接调用 Multica HTTP API（`GET /api/issues`），
> 每条包含状态图标、编号、标题、优先级与指派人，列表紧凑避免刷屏。

指令受会话过滤配置（黑白名单）控制。

### 🔐 管理员权限

`/multica` 通过 AstrBot 标准的指令注册方式挂载，属于 AstrBot 的**一等指令**。
你可以在 **AstrBot WebUI → 指令管理** 中找到 `/multica`，并一键将其设为
**仅管理员** 或 **成员可**，实现 ChatOps 指令的权限回收。

---

## 🔌 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/plug/astrbot_plugin_multica_bridge/config` | 获取当前配置（token 脱敏） |
| POST | `/api/plug/astrbot_plugin_multica_bridge/actions/save_config` | 保存配置 |
| POST | `/api/plug/astrbot_plugin_multica_bridge/actions/test_connection` | 测试连接 |

---

## 🛠️ 开发

```bash
# 克隆仓库
git clone https://github.com/Eason4869/astrbot_plugin_multica_bridge.git
cd astrbot_plugin_multica_bridge

# 安装到 AstrBot（开发模式）
# 将本目录软链接或复制到 AstrBot/data/plugins/
```

---

## 📝 更新日志

详见 [CHANGELOG.md](CHANGELOG.md)

---

## 📄 许可证

MIT

---

<p align="center">
  <img src="assets/banner-anime-2.webp" width="360" alt="Thanks for reading" />
</p>

<p align="center">
  <sub>Made with 💜 · 如果这个项目对你有帮助，欢迎点个 ⭐ Star</sub>
</p>
