# Changelog

## [0.5.0] - 2026-08-11

### Added

- 新增 `/multica workspace list` 指令：列出当前 Token 可访问的所有工作区（名称、slug、id）
- 新增 `/multica workspace select <id|slug>` 指令：切换当前工作区，通过 `save_plugin_config`
  原子写入插件自有 `config.json` 的 `workspace_id` 字段，重启后仍生效
- 新增 `/multica workspace create <名称> [--slug slug] [--desc 描述]` 指令：
  调用 `POST /api/workspaces` 创建工作区，slug 缺省时按名称自动生成（小写字母/数字/连字符）
- `MulticaClient` 新增 `list_workspaces()`、`create_workspace()`，并重构 `test_connection()`
  复用列表接口；`_ensure_workspace_id()` 改为按已配置的 workspace_id/slug 精确匹配当前工作区
- `/multica help` 与 WebUI「指令说明」卡片同步新增 workspace 命令

### Why

- 用户需要在不打开 Web 控制台的情况下查看/切换多个工作区，并直接在聊天中创建新工作区；
  工作区选择仅持久化配置，无独立 API 调用。

## [0.4.0] - 2026-08-11

### Removed

- 移除 `/multica sync` 指令、`MulticaClient.sync_data()` 及 WebUI `/actions/sync` 端点：
  Multica API 不存在 `POST /api/data/sync` 端点（实测返回 `HTTP 404: 404 page not found`），
  该「数据同步」功能从无服务器端支撑，无法正常工作。
- 移除 `sync_reports`、`sync_interval_minutes` 配置项及 WebUI「同步设置」区域。

### Why

- 用户报告 `/multica sync` 返回 `同步失败: HTTP 404: 404 page not found`。
- 排查确认：Multica API 未提供任何通用数据同步端点，插件不应再请求不存在的路径。

## [0.3.0] - 2026-08-11

### Added

- 新增 `/multica issue create <标题> [--desc 描述]` 指令：通过 HTTP API 直接创建 Issue，不依赖本机安装 `multica` CLI / PATH
- `MulticaClient.create_issue()`：调用 `POST /api/issues`，字段与 CLI 对齐（title/description/priority/status/assignee_id/project_id/parent_issue_id/due_date/labels）
- WebUI 设置页新增「指令说明」卡片，列出全部 `/multica` 指令用法

### Fixed

- 修复 `POST /api/issues` 返回 `HTTP 400: workspace_id or workspace_slug is required`：
  Multica API 通过 **query 参数**识别工作区（`?workspace_id=...`），body 中的 `workspace_id` 会被忽略。
  `create_issue()` 改为将工作区放入 URL query，并在无法确定工作区时给出明确中文报错。

### Why

- 用户在 QQ 要求新建 Issue 时，AstrBot 的 LLM agent 通过 `astrbot_execute_shell` 调用 `multica` CLI，
  但 AstrBot 进程环境是启动时快照：若 `multica` 安装/加入 PATH 发生在 AstrBot 启动之后，
  其子进程（PowerShell）找不到 `multica`，LLM 便误报“本机未安装 multica”。
- 本版本提供不依赖 CLI 的创建路径；同时保持 CLI 可用（AstrBot 重启后 PATH 即刷新）。

## [0.2.2] - 2026-08-11

### Fixed

- 修复 API 端点：`/api/workspace` → `/api/workspaces`（与实际 Multica API 匹配）
- 修复默认 API 地址：`http://localhost:8080` → `https://multica.ai`
- WebUI 提示文字同步更新

### Changed

- `workspace_id` 改为可选：留空时自动从 `/api/workspaces` 获取 UUID 并缓存，用户只需配 `api_url` + `token` 两项即可
- `test_connection()` 成功时自动缓存 workspace_id 和 workspace_name
- 401 错误给出明确的 Token 失效提示
## [0.2.1] - 2026-08-11

### Fixed

- `/multica` 指令修复：将命令注册从废弃的 `register_event_listener` 迁移到 `star_handlers_registry` + `StarHandlerMetadata` + `CommandFilter`，兼容 AstrBot v4.27.2+
- `_on_command` 文本解析适配 CommandFilter 模式（前缀已被剥离），同时兼容旧路径

## [0.2.0] - 2026-08-11

### Added

- 会话过滤配置：群聊/私聊的黑白名单模式切换，各自的黑白名单列表
- `/multica` 系列命令：`help`、`status`、`sync`，支持在聊天中直接操作
- 项目 logo（SVG）

### Changed

- README 大幅扩展：添加 Multica 文档链接、API 地址与 Token 获取教程、命令用法说明
- WebUI 设置页新增会话过滤配置区域

### Fixed

- WebUI 保存时 token 被 GET 返回的脱敏值覆盖的问题（前后端双重防护）

## [0.1.0] - 2026-08-11

### Added

- 初始版本
- Multica 连接测试功能（`test_connection`）
- 数据同步功能（`sync_data`）
- WebUI 设置页：所有配置项可视化编辑，自动保存热生效
- 配置管理：默认值合并、类型校验、持久化
- Token 脱敏：API 返回时自动掩码敏感字段
- 4 个 REST API 端点：config / save_config / test_connection / sync
