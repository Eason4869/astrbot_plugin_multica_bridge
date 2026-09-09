<div align="center">

![:name](https://count.getloli.com/@astrbot_plugin_multica_bridge?name=astrbot_plugin_multica_bridge&theme=minecraft&padding=6&offset=0&align=top&scale=1&pixelated=1&darkmode=auto)

<img src="https://raw.githubusercontent.com/Eason4869/astrbot_plugin_multica_bridge/main/logo.svg" width="110" height="110" alt="Multica Bridge Logo" />

# AstrBot Multica 桥接插件

*AstrBot × Multica · 一键接入 · ChatOps 赋能*

<img src="https://img.shields.io/badge/version-0.8.1-6366f1" alt="version 0.8.1" />
<img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python 3.10+" />
<img src="https://img.shields.io/badge/AstrBot-%E2%89%A54.27.2-4f8cff" alt="AstrBot >=4.27.2" />
<img src="https://img.shields.io/badge/License-MIT-yellow" alt="MIT License" />

<img src="https://raw.githubusercontent.com/Eason4869/astrbot_plugin_multica_bridge/main/assets/banner-anime.jpg" width="640" alt="Anime banner" />

将 AstrBot QQ 机器人接入 [Multica](https://multica.ai)，在聊天里完成连接测试、建 Issue、管工作区/项目、看收件箱。

</div>

---

## 目录

1. [功能](#-功能)
2. [安装](#-安装)
3. [配置](#️-配置)
4. [获取 API / Token](#-获取-api--token)
5. [指令](#-指令)
6. [权限](#-权限)
7. [API 端点](#-api-端点)
8. [开发](#-开发)
9. [更新日志 / 许可](#-更新日志--许可)

---

## ✨ 功能

| 类别 | 说明 |
|------|------|
| 连接 | 一键测 Multica 连通性，显示当前工作区 / 项目 |
| Issue | 聊天内创建 Issue，可带优先级、状态、指派人、项目、截止日期、标签 |
| 工作区 | 列出 / 切换 / 新建；切换会写入插件配置，重启仍有效 |
| 项目 | 列出 / 切换 / 新建；新建 Issue 默认进当前项目 |
| 收件箱 | 查看最近 Issue 与进展（可按未完成 / 已完成过滤） |
| 配置 | WebUI 修改后热生效；API 返回时 Token 自动脱敏 |
| 过滤 | 群聊 / 私聊黑名单、白名单或关闭 |
| 权限 | 子指令在 AstrBot「指令管理」中独立配置「仅管理员 / 成员可」 |
| 语言 | 设置页中英文，跟随 AstrBot 界面语言 |

---

## 📦 安装

**方式一 · 插件市场**

1. AstrBot WebUI → 插件管理  
2. 添加仓库：`https://github.com/Eason4869/astrbot_plugin_multica_bridge`  
3. 安装  

**方式二 · 手动**

```bash
cd AstrBot/data/plugins
git clone https://github.com/Eason4869/astrbot_plugin_multica_bridge.git
```

---

## ⚙️ 配置

**唯一入口：** WebUI → 插件 → Multica桥接 → **设置**（改完即存、热生效）。

> 本插件**不用**插件管理里的「齿轮」（`_conf_schema.json`）。  
> 齿轮配置由 AstrBot 另存，插件运行时不读取，容易和设置页不同步。

### 连接

| 配置项 | 类型 | 默认 | 说明 |
|--------|------|------|------|
| `enabled` | bool | `true` | 启用 / 停用插件 |
| `api_url` | str | `https://multica.ai` | Multica API 基地址 |
| `token` | str | — | API 认证 Token |
| `workspace_id` | str | — | 工作区 UUID（可留空自动获取） |
| `project_id` | str | — | 项目 UUID（也可用指令切换） |

### 会话过滤

| 配置项 | 类型 | 默认 | 说明 |
|--------|------|------|------|
| `group_chat_mode` | str | `blacklist` | 群聊：`blacklist` / `whitelist` / `disabled` |
| `group_chat_list` | list | `[]` | 群聊 ID 列表 |
| `private_chat_mode` | str | `blacklist` | 私聊：同上 |
| `private_chat_list` | list | `[]` | 用户 ID 列表 |

---

## 🔑 获取 API / Token

### API 地址

| 模式 | 地址 |
|------|------|
| Multica Cloud（推荐） | `https://multica.ai` |
| 自托管 | 你的 Multica 服务器地址 |

### 认证 Token

1. 登录 Multica Web 控制台  
2. **设置 → API 密钥**（Settings → API Keys）  
3. 创建密钥（名称例如 `AstrBot Bridge`）  
4. 复制 Token，填入插件设置里的「认证 Token」

### 工作区 / 项目 UUID

一般**不用手填**：首次调用会自动解析工作区；也可用聊天指令列出 / 切换。

若要在平台侧查看，可用 Multica CLI / Web 的查看命令，JSON 里的 `id` 即 UUID。

> 插件只通过 **HTTP API** 交互，不依赖本机 Multica CLI。

官方文档：[快速上手](https://multica.ai/docs/zh/cloud-quickstart) · [认证与令牌](https://multica.ai/docs/zh/auth-tokens)

---

## 💬 指令

在允许的群聊或私聊中发送：

| 指令 | 说明 |
|------|------|
| `/multica` | 不带子指令时显示指令树 |
| `/multica help` | 帮助 |
| `/multica status` | 连接、工作区 / 项目、脱敏 Token |
| `/multica issue create <标题> [选项]` | 新建 Issue |
| `/multica inbox [数量] [open\|done]` | 收件箱（默认 10 条；`open` 未完成 / `done` 已完成） |
| `/multica workspace list` | 列出工作区 |
| `/multica workspace select <id\|slug>` | 切换工作区（写入配置） |
| `/multica workspace create <名称> [--slug …] [--desc …] [--context …]` | 新建工作区 |
| `/multica project list` | 列出项目 |
| `/multica project select <id>` | 切换项目（新建 Issue 默认进该项目） |
| `/multica project create <标题> [--desc …]` | 新建项目 |

### `issue create` 选项

| 参数 | 取值 | 说明 |
|------|------|------|
| `--desc` | 文本 | 描述 |
| `--priority` | `紧急` / `高` / `中` / `低`（或英文） | 优先级 |
| `--status` | `backlog` `todo` `in_progress` `in_review` `done` `cancelled` | 初始状态 |
| `--assignee` | id | 指派人 |
| `--project` | id | 覆盖当前项目 |
| `--due` | `YYYY-MM-DD` | 截止日期 |
| `--labels` | `标签1,标签2` | 标签（中英文逗号均可） |

示例：

```text
/multica issue create 修复登录失败 --desc 用户反馈登录超时 --priority 高 --labels 后端,线上
```

说明：

- `issue create` / `inbox` 均走 **HTTP API**，不要求本机安装 Multica CLI  
- `inbox` 含状态图标、编号、标题、优先级、指派人；指派人名称有 5 分钟缓存  
- 受会话过滤限制；插件停用时会明确提示  

---

## 🔐 权限

`/multica` 为指令组，子指令在 **WebUI → 指令管理** 中可分别设权限：

| 子指令 | 建议权限 |
|--------|----------|
| `inbox` / `status` / `help` | 成员可 |
| `workspace create` / `project create` | 仅管理员 |
| `workspace select` / `project select` | 仅管理员（会改配置） |

权限保存在 AstrBot 的 `alter_cmd`，重启后自动回植。

---

## 🔌 API 端点

设置页通过插件 Pages bridge 调用：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/plugins/extensions/<插件名>/config` | 读配置（Token 脱敏） |
| POST | `…/actions/save_config` | 增量保存 |
| POST | `…/actions/test_connection` | 测连接 |

旧路径 `/api/plug/<插件名>/…` 仍可用。`<插件名>` 默认为目录名 `astrbot_plugin_multica_bridge`。

---

## 🛠️ 开发

```bash
git clone https://github.com/Eason4869/astrbot_plugin_multica_bridge.git
cd astrbot_plugin_multica_bridge

# 将本目录放入或软链到 AstrBot/data/plugins/

python -m pip install ruff pytest pyyaml
ruff check .
python -m pytest
```

| 路径 | 说明 |
|------|------|
| `main.py` | 指令组与子指令 |
| `multica_client.py` | Multica HTTP 客户端 |
| `web_api.py` | 设置页 REST |
| `config.py` | 配置读写与类型转换 |
| `pages/settings/index.html` | 设置页 |
| `.astrbot-plugin/i18n/` | 中英文文案 |
| `tests/` | 单元测试 |

---

## 📝 更新日志 / 许可

- 更新日志：[CHANGELOG.md](https://github.com/Eason4869/astrbot_plugin_multica_bridge/blob/main/CHANGELOG.md)
- 许可证：[MIT License](https://github.com/Eason4869/astrbot_plugin_multica_bridge/blob/main/LICENSE)

---

<div align="center">
  <img src="https://raw.githubusercontent.com/Eason4869/astrbot_plugin_multica_bridge/main/assets/banner-anime-2.webp" width="360" alt="Thanks for reading" />
  <p><sub>Made with 💜 · 有帮助的话欢迎点个 ⭐ Star</sub></p>
</div>
