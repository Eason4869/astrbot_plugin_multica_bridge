# AstrBot Multica 桥接插件

<p align="center">
  <img src="logo.svg" width="96" height="96" alt="Multica Bridge Logo" />
</p>

将 AstrBot QQ 机器人接入 [Multica](https://multica.ai) 平台，实现连接测试、数据同步、ChatOps 等功能。

## 功能

- **连接测试**：一键验证 Multica API 连通性
- **配置热生效**：WebUI 中修改配置后即时生效，无需重载
- **数据同步**：支持将 AstrBot 运行数据同步到 Multica 工作区
- **Token 安全**：API 返回配置时自动脱敏敏感字段，防止误保存覆盖
- **会话过滤**：支持群聊/私聊的黑白名单模式，精准控制插件生效范围
- **命令交互**：支持 `/multica` 系列指令，在聊天中直接操作

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

### 同步配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `sync_reports` | bool | `false` | 启用自动同步 |
| `sync_interval_minutes` | int | `60` | 同步间隔（分钟） |

### 会话过滤

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `group_chat_mode` | str | `blacklist` | 群聊过滤模式：`blacklist` / `whitelist` / `disabled` |
| `group_chat_list` | list | `[]` | 群聊 ID 列表（根据模式排除或允许） |
| `private_chat_mode` | str | `blacklist` | 私聊过滤模式：`blacklist` / `whitelist` / `disabled` |
| `private_chat_list` | list | `[]` | 用户 ID 列表（根据模式排除或允许） |

## 如何获取 Multica API 地址和 Token

### 1. 获取 API 地址

一般为 `https://multica.ai`（Multica Cloud），自托管则填入你的 Multica 服务器地址。

### 2. 获取认证 Token

1. 登录 Multica Web 控制台
2. 进入 **设置 → API 密钥**（或 **Settings → API Keys**）
3. 点击 **创建密钥**，输入名称（如 `AstrBot Bridge`）
4. 复制生成的 Token，填入本插件的认证 Token 配置项

> 更多细节请参考 Multica 官方文档：
> - [快速上手](https://multica.ai/docs/zh/cloud-quickstart)
> - [认证与令牌](https://multica.ai/docs/zh/auth-tokens)

### 3. 获取工作区 ID（可选）

插件会自动从 API 获取工作区 ID，**一般无需手动填写**。如果你需要手动指定，可在 Multica Web 控制台的工作区设置中查看 UUID。

## 指令

在任意允许的群聊或私聊中发送以下命令：

| 指令 | 说明 |
|------|------|
| `/multica help` | 显示帮助信息 |
| `/multica status` | 检查 Multica 连接状态 |
| `/multica sync` | 手动触发一次数据同步 |

指令受会话过滤配置（黑白名单）控制。

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/plug/astrbot_plugin_multica_bridge/config` | 获取当前配置（token 脱敏） |
| POST | `/api/plug/astrbot_plugin_multica_bridge/actions/save_config` | 保存配置 |
| POST | `/api/plug/astrbot_plugin_multica_bridge/actions/test_connection` | 测试连接 |
| POST | `/api/plug/astrbot_plugin_multica_bridge/actions/sync` | 同步数据 |

## 开发

```bash
# 克隆仓库
git clone https://github.com/Eason4869/astrbot_plugin_multica_bridge.git
cd astrbot_plugin_multica_bridge

# 安装到 AstrBot（开发模式）
# 将本目录软链接或复制到 AstrBot/data/plugins/
```

## 更新日志

详见 [CHANGELOG.md](CHANGELOG.md)

## 许可证

MIT
