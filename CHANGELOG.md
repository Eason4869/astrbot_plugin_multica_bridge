# Changelog

## [1.1.0] - 2026-10-19

### Changed

- 群聊工作模式仅转发开启者的文字，其他成员继续使用 AstrBot；换开启者新建 Chat，旧版无开启者记录的活动会话暂停。
- 统一 Multica 放行用户名单，支持 UID、私聊 UMO、群聊 UMO；移除群聊/私聊黑白名单控件。空名单拒绝所有人，未放行按指定文案回复；指令默认不要求管理员。
- 主帮助收敛为 7 个工作入口，Issue/inbox 保留高级入口，旧 workspace/project 命令与权限兼容。
- WebUI 展示三种放行格式及作用范围，新增工作区/项目选项、会话开启者与暂停原因，调整深浅主题和移动端布局。

### Added

- 口语进入工作模式：进入multica模式、切换为multica工作等；复用安全路由与进入权限，不支持自然语言退出。
- 结构化意图和字段校验；规则优先，模型解析限时 10 秒、同窗口并发 1、同用户 5 秒一次。
- 自然语言创建 Issue 先预览，120 秒内本人短码确认；过期、跨用户、重复或上下文变化时不提交。

### Fixed

- 自然语言不能绕过指令禁用或管理员/自定义过滤器；总开关检查位于模型调用前。
- 错误工作区不再回退到首项；名称和前缀歧义拒绝选择；切换工作区清空旧项目并验证归属。
- stop 使本地旧排队消息失效，并在在途提交结算后请求远端停止；退出保持独立语义。
- 保留正文中的 multica，校验日期、否定和复合请求，屏蔽服务器原始错误正文。
- 快速返回结果时不再重复发送成功回执；退出和卸载取消迟到提示。

验证范围见 docs/verification-1.1.0.md；真实 QQ、Multica 和模型联调仍需部署环境验收。本轮只准备本地更新，不宣称已远程发布。

## [1.0.0] - 2026-10-19

从 0.9.0 升级为连续对话工作模式，合并至 `main`，以 `v1.0.0` 标签发布。此前本地准备的 0.10.0 改造统一纳入本次 1.0.0，未单独发布 0.10.0。

### Added

- `/multica` 进入连续 Chat 工作模式，`exit` 退出，`new` 新对话、`agent` 选智能体、`stop` 停止执行。
- 群聊按群隔离并共用 Chat，私聊按窗口隔离；状态在重载后恢复。回复统一标记 `【来自 Multica｜工作模式】`。
- 入口接管保留全局访问控制，跳过其他插件指令过滤、会话等待与默认模型；失败时不降级到普通模型。
- HTTP Chat 客户端、轮询回传、长消息分段、已处理输入去重、超时提交结果核对与退出后迟到回复抑制。
- 工作台 WebUI：连接测试、工作会话列表与定向退出、智能体列表、访问规则、普通模式高级设置；暗色和移动端适配。

### Fixed

- 沿用 0.9.0 的插件标识、数据目录和配置字段；初始化不写配置，增量保存保留旧 URL、Token 及未知字段。
- 首次写入前备份 config.json；空白/脱敏 Token 不覆盖已保存凭据，清除需明确操作。
- 配置读取失败时保留原文件，禁止默认配置覆盖；配置和工作状态使用独立原子写入。
- 退出或卸载期间取消本地处理、抑制迟到回复；等待远端响应期间配置或访问规则变化后重新检查权限。
- 工作模式开关关闭时保留原管理指令；阻止机器人自身消息在工作模式内回环转发。
- 设置页忽略旧连接测试结果，防止清除 Token 与后续编辑互相覆盖；保存期间继续编辑不会丢失新值。

### Changed

- README 按安装升级、工作模式、会话隔离、WebUI 与指令重新组织，补充正式版安装说明、界面预览和常见问题；图片和版本文档链接固定到 v1.0.0。
- 设置页及安装元数据统一为 1.0.0；提供不包含部署配置或运行数据的源码 ZIP 构建脚本。

### Validation

- Python 3.10 与 3.12 本地各 114 项回归通过，覆盖旧配置加载、保存、重载及安装包覆盖升级。
- Edge 桌面、390px / 320px、深浅主题和英文布局通过；包含自动保存及连接检测竞态检查。
- GitHub Actions 增加 Python 双版本及上游管线源码集成检查；真实 QQ / Multica 联调仍待部署环境验收。

### Compatibility

- 保留原有 Issue、工作区、项目、收件箱与普通模式自然语言控制。
- 首版工作消息支持文本；图片、文件、语音明确提示，不转交其他插件或 AstrBot 模型。
- 使用 Multica Chat App API；部署版本需具备 Chat 能力。退出不取消远端任务，可先 stop 再 exit。
- 路由兼容性以管线形状检测及 AstrBot 4.27.2 / 4.29.1 上游源码集成测试为基础；QQ 实际环境需另行验证。

## [0.9.0] - 2026-09-19

### Added

- **自然语言控制**：消息中包含关键词（默认 `multica`，可配置）即可自动识别
  Multica 意图，无需 `/` 指令前缀。例如：
  - `multica 建个issue：修复登录，优先级高`
  - `multica 收件箱 10 open`
  - `multica 切换到项目 前端重构`
  - `multica status` / `multica 帮助`
- 解析策略为**规则优先 + 可选 LLM 回退**：
  - 本地规则覆盖常见中英文口语与无斜杠指令写法，抽取标题/描述/优先级/
    状态/标签/截止日期等字段后，复用既有子指令实现；
  - 规则无法识别时，若启用 `nl_llm_enabled`，则调用 AstrBot 当前 LLM
    Provider 将复杂句子解析为结构化意图 JSON；
  - 仅提及关键词的闲聊（如「multica是什么」）不拦截，仍交回 LLM 对话。
- 新增配置项（WebUI 热生效）：`nl_enabled`、`nl_keyword`、`nl_llm_enabled`。
- 设置页新增「自然语言控制」分区；帮助文案、README、i18n 同步更新。
- 新增 `nl_control.py` 意图解析模块与单元测试。

### Fixed

- **允许 README 页内锚点**：0.8.1 起目录使用 `(#-功能)` 形式的页内锚点，
  而 `test_readme_images_use_absolute_urls` 会把它们当成相对路径导致 CI
  失败。纯 `#anchor` 在 markdown 中合法，且不会解析到 AstrBot Dashboard
  域名下，测试改为允许页内锚点；README 目录链接同时改为仓库绝对 URL，
  与 AstrBot 渲染行为对齐。

### Changed

- GitHub Actions CI：`actions/checkout` / `actions/setup-python` 升到当前
  major，消除 ubuntu-latest 上 Node.js 20 的弃用警告。

### Why

- 结构化 `/multica issue create …` 参数齐全但门槛高，群聊里用户更习惯
  直接说「帮我建个 issue」。此前只能依赖主 LLM 误调 shell/CLI，既不可靠
  又易失败；本版把控制面收进插件内部，规则兜底、LLM 可选。

## [0.8.1] - 2026-09-09

### Fixed

- 修复已知问题

### Changed

- README 可读性整理（目录、表格化、精简说明）

## [0.8.0] - 2026-09-09

### Added

- **指令组重构**：`/multica` 改为 AstrBot 标准指令组，子指令按树形注册：
  `help` / `status` / `inbox`、`issue create`、`workspace list|select|create`、
  `project list|select|create`。每条子指令在「指令管理」中都是独立条目，
  可**分别**设置「仅管理员 / 成员可」（例如 `inbox` 放开给成员，
  `workspace create` 收紧给管理员）；直接发送 `/multica` 会由 AstrBot
  自动渲染指令树。
- `issue create` 补齐可选参数：`--priority`（支持中文 紧急/高/中/低）、
  `--status`、`--assignee`、`--project`、`--due`、`--labels`（逗号分隔）。
- `status` 现在展示当前工作区名称/id/slug、项目标题、脱敏 Token 与 API 地址。
- WebUI 支持中英双语（`.astrbot-plugin/i18n/{zh-CN,en-US}.json`），
  通过 bridge 的 `t()` 自动跟随 AstrBot 界面语言。
- 新增 `requirements.txt`、`LICENSE`、`ruff` 配置、GitHub Actions CI 与
  `tests/` 单元测试（配置强转、会话过滤、工作区/项目查找、页面与文档一致性）。

### Fixed

- **修复布尔配置强转错误**：旧实现 `bool(value)` 会把字符串 `"false"` 判为
  `True`（非空字符串恒真），直接调 REST 保存时会写错值；改为按
  `1/true/yes/on` 等白名单解析，无法识别时回退默认值。
- **修复 WebUI 暗色模式失效**：旧代码依赖 `bridge.isDark` 与
  `bridge.onThemeChange`，而 AstrBot 的页面 bridge 并不提供这两个成员，
  导致暗色主题永远不生效；改用 `getContext()` / `onContext()` 读取
  `isDark`，并让样式同时匹配 `[data-theme="dark"]`。
- **修复 WebUI 保存覆盖聊天侧配置**：旧实现每次保存都回写整份配置，
  若用户在聊天中用 `workspace select` 切换了工作区，再改任意设置就会把
  旧的 `workspace_id` 写回；改为只提交被改动过的字段（增量保存）。
- 修复 Web API 注册与请求异常被静默吞掉（无日志）的问题，改为记录错误日志。
- `inbox` 性能：指派人名称解析新增 TTL 缓存，并只查询当前展示的 Issue
  涉及的 id，避免每次额外发起 3 个请求。
- **修复 README 图片在 AstrBot 中不显示**：AstrBot 直接用 markdown-it 渲染
  插件目录下的 README，且不会重写相对路径，`assets/banner.jpg` 之类的写法
  会解析到 Dashboard 域名下导致 404；已全部改为绝对 URL
  （`raw.githubusercontent.com`），仓库内文档链接同理。

### Changed

- 请求体读取改用 AstrBot 官方 `astrbot.api.web.request`（保留 Quart 回退）。
- Web API 路由前缀按插件目录名动态生成，插件目录改名后不再全部 404。
- 日志改用 Star 提供的插件级 logger（缺失时回退全局 logger）。
- `astrbot_version` 提升到 `>=4.27.2`：指令管理的权限回植与插件 Pages
  Web API 依赖该版本。
- 版本提升至 0.8.0。

### Why

- 单一 `/multica` 指令只能整体授权，无法满足“查看类指令放开、写入类指令收紧”
  的实际诉求；AstrBot 指令组天然支持逐条授权。
- 用户反馈暗色界面下设置页仍是亮色，排查确认 bridge 并不暴露
  `isDark` / `onThemeChange`。
- 新增 CI 与测试用于锁定上述修复，防止回归。

## [0.7.0] - 2026-09-03

### Fixed

- **修复「/multica 设为仅管理员」在 AstrBot 指令管理中不生效的问题**。
  原因：命令监听此前在 `initialize()` 里手动追加到 `star_handlers_registry`，
  而 AstrBot 加载插件时会先扫描该插件的已注册指令并回植持久化的「仅管理员」
  权限过滤器（`alter_cmd`），随后才调用 `initialize()`；由此该监听在权限回植
  后才注册，导致管理员配置永远无法应用。
  现改为在类定义阶段通过 AstrBot 标准 `@command` 装饰器注册，使 `/multica`
  在指令管理中被视为一等指令，可正常切换为「仅管理员 / 成员」。

### Changed

- WebUI 设置页全面美化：渐变主题、卡片化分区、图标化章节、加载动效、暗色适配与
  可读性优化；同时新增「可在指令管理中将 /multica 设为仅管理员」的权限提示。
  页面字段 ID、自动保存与连接测试逻辑保持不变，桥接契约向后兼容。

### Other

- 补齐 `workspace create` 的 `--context` 参数在帮助与用法提示中的说明（此前缺省）。
- version 提升至 0.7.0。

### Why

- 用户反馈：在 AstrBot 的管理行为中把 `/multica` 指令设置为管理员失败（不拦截
  普通用户），根源是指令在加载期之后才注册，权限配置无法被回植应用。

## [0.6.0] - 2026-08-12

### Removed

- 移除 `_conf_schema.json`：取消 AstrBot 插件管理页面中的「齿轮」配置入口。
  AstrBot 通过 `_conf_schema.json` 生成的配置保存于其独立存储中，并在实例化插件时传入
  `config` 参数；但插件 `initialize()` 仅从插件自有 `plugin_data/<name>/config.json`
  构建运行配置，从未合并该 `config`，导致齿轮入口的修改不生效。
- WebUI 设置页已覆盖全部配置项（连接参数 + 会话过滤），故统一以 WebUI 设置页为唯一配置入口。

### Why

- 用户反馈：WebUI 中配置正确生效，但 astrbot 插件页面齿轮入口修改配置不生效。
- 排查确认：两套配置来源难以可靠同步（AstrBot 会用 schema 默认值覆盖未在齿轮中
  修改过的字段，合并方向无论谁优先都会破坏另一入口的既有配置），故选取消齿轮入口。

## [0.5.0] - 2026-08-12

### Added

- 新增 `/multica workspace list` 指令：列出当前 Token 可访问的所有工作区（名称、slug、id）
- 新增 `/multica workspace select <id|slug>` 指令：切换当前工作区，通过 `save_plugin_config`
  原子写入插件自有 `config.json` 的 `workspace_id` 字段，重启后仍生效
- 新增 `/multica workspace create <名称> [--slug slug] [--desc 描述]` 指令：
  调用 `POST /api/workspaces` 创建工作区，slug 缺省时按名称自动生成（小写字母/数字/连字符）
- `MulticaClient` 新增 `list_workspaces()`、`create_workspace()`，并重构 `test_connection()`
  复用列表接口；`_ensure_workspace_id()` 改为按已配置的 workspace_id/slug 精确匹配当前工作区
- `/multica help` 与 WebUI「指令说明」卡片同步新增 workspace 命令
- 新增 `/multica inbox [数量] [open|done]` 指令：在聊天中查看工作区收件箱（最近 Issue 及进展）
  - 默认显示最近 10 条，按更新时间倒序，每条含状态图标、编号、标题、优先级、指派人
  - `open` 仅显示未完成（非 done/cancelled）；`done` 仅显示已完成/已取消
  - 数量参数生效（1-50，防止刷屏）
- `MulticaClient.list_issues()`：调用 `GET /api/issues`，query 参数传 workspace_id（与 `create_issue` 一致），支持 status/limit/sort/direction 过滤
- `MulticaClient.resolve_assignee_names()`：best-effort 解析指派人名称（智能体/团队/成员），端点失败自动降级，不影响主流程
- `/multica help`、README、WebUI 指令说明同步新增 inbox 命令
- 新增 `/multica project list` 指令：列出当前工作区下的所有项目（标题、id，当前项目带 ✓ 标记）
- 新增 `/multica project select <id>` 指令：切换当前项目，通过 `save_plugin_config`
  原子写入插件自有 `config.json` 的 `project_id` 字段，重启后仍生效；
  `create_issue` 已支持 `project_id` 传递，切换后新建 Issue 默认进入所选项目
- 新增 `/multica project create <标题> [--desc 描述]` 指令：调用 `POST /api/projects`
  创建项目（query 参数传 workspace_id，title 必填、description 可选）
- `MulticaClient` 新增 `list_projects()`、`create_project()`、`find_project()`：
  列表与创建均复用 `_ensure_workspace_id()` 解析工作区，query 参数传 workspace_id（与 `create_issue` 一致）
- `/multica help`、README、WebUI 指令说明同步新增 project 命令

### Why

- 用户需要在不打开 Web 控制台的情况下查看/切换多个工作区，并直接在聊天中创建新工作区；
  工作区选择仅持久化配置，无独立 API 调用。
- 用户希望在聊天中随时掌握 Multica Issue 的状态与进展，无需打开 Web 控制台。
- API 不支持按 `updated_at` 排序（实测报错），故拉取较新窗口后在本地完成排序。
- 用户希望为新建 Issue 指定所属项目：选择项目仅持久化配置（`project_id`），
  `create_issue` 已支持该字段，无需新增额外参数。

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
