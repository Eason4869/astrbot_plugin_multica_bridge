# AstrBot Multica 桥接插件

将 AstrBot 接入 [Multica](https://multica.ai) 平台，实现连接测试、数据同步等功能。

## 功能

- **连接测试**：一键验证 Multica API 连通性
- **配置热生效**：WebUI 中修改配置后即时生效，无需重载
- **数据同步**：支持将 AstrBot 运行数据同步到 Multica 工作区
- **Token 安全**：API 返回配置时自动脱敏敏感字段

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

所有配置项均可在 AstrBot WebUI → 插件 → Multica桥接 → 设置 页面中修改。

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enabled` | bool | `true` | 启用/停用插件 |
| `api_url` | str | `http://localhost:8080` | Multica API 基地址 |
| `token` | str | — | Multica API 认证 Token |
| `workspace_id` | str | — | Multica 工作区 UUID |
| `project_id` | str | — | Multica 项目 UUID（可选） |
| `sync_reports` | bool | `false` | 启用自动同步 |
| `sync_interval_minutes` | int | `60` | 同步间隔（分钟） |

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/plug/astrbot_plugin_multica_bridge/config` | 获取当前配置 |
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

## 许可证

MIT
