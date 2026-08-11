# Changelog

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
