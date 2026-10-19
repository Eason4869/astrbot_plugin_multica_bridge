# Multica Bridge 精简与自然语言边界更新实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复权限与上下文风险，将日常入口收敛到工作对话，并给自然语言操作建立明确的识别、授权、澄清和确认边界。

**Architecture:** 命令、规则和模型输出先转成统一的结构化操作，再经过授权和参数校验。工作模式继续使用独立 Chat 转发链路；低频全局管理转移到 WebUI，兼容期保留旧 handler。

**Tech Stack:** Python 3.10+、asyncio、aiohttp、AstrBot 4.27.2+、原生 HTML/CSS/JavaScript、pytest、Ruff、现有浏览器验证脚本。不引入 Docker 或新的代理运行框架。

**Spec:** `docs/superpowers/specs/2026-10-19-multica-review-and-simplification-design.md`。该文件是本计划的审查证据和设计依据；两份文件均等待用户评审，本轮不开始实施。

## Global Constraints

- Python 最低 3.10，AstrBot 最低 4.27.2；继续验证原有两个 AstrBot 源码版本。
- 插件标识、数据目录、api_url/token 旧字段不变；加载不回写，写入前备份，损坏配置保留。
- 工作模式按平台实例、自身账号和窗口隔离；群内上下文共享，来源前缀保持。
- 退出不会自动取消远端任务；stop 保持工作模式；工作失败不回落普通模型。
- 主菜单 7 个入口；高级 Issue/inbox 保留；v1.1 不删除旧命令或别名。
- NL 可执行 action 为 help/status/inbox/issue_create/work_enter；Issue 写入需本人短码确认，草稿期限 120 秒；work_enter 复用进入命令的权限和安全流程。
- Provider 解析超时 10 秒，不自动重试；同窗口并发最多 1，同用户每 5 秒最多 1 次。
- 日期以 Asia/Shanghai 解释；数量 1–50；名称须唯一精确匹配，ID 前缀至少 8 位且唯一。
- 页面保留现有布局、字体、色彩体系、双语、浅色/暗色和手机适配。
- 不在本轮推送、发布或变更线上配置；真实联调与发布需后续实施任务安排。

## Review Focus

- 成员借自然语言调用管理员或被禁用的命令：必须拒绝，写 API 调用数为 0（任务 1）。
- 显式错误工作区、同名项目和残留项目归属：不得静默选择或跨工作区写入（任务 2）。
- 停止时存在本地排队及结果不确定的 POST：旧排队失效，不宣告未确认的远端停止成功（任务 3）。
- 否定句、复合句、正文包含触发词和模型恶意字段：不得改变正文或产生未经确认的写入（任务 4、5）。
- 用户切配置、换 Chat、退出或改权限后再确认旧草稿：旧确认失效且不能重复提交（任务 5）。

## 文件职责

| 文件 | 责任 |
| --- | --- |
| `actions.py`（新增） | ActionRequest、action 到命令映射、统一授权与分发入口 |
| `nl_control.py`（调整） | 调用前缀、规则、模型协议和严格字段解析；不发业务 HTTP 请求 |
| `pending_intents.py`（新增） | 120 秒内存草稿、本人短码确认、一次消费 |
| `main.py`（调整） | AstrBot 注册、统一入口、帮助；渐进迁出相关职责 |
| `multica_client.py` / `chat_client.py`（调整） | 工作区/资源解析与 HTTP 边界，保留两个客户端现有职责 |
| `work_mode.py`（调整） | 工作控制、停止屏障、提交有效性 |
| `work_mode_integration.py` / `astrbot_compat.py`（调整） | 复用实际 command handler 的权限、兼容入口 |
| `web_api.py` / `pages/settings/index.html`（调整） | 管理选择、验证、兼容指引和模式展示 |
| `tests/`、文档和双语资源（调整） | 行为验收、迁移、准确的能力说明 |

## Task 1：统一权限与停用边界

**Files:** 新建 `actions.py`；修改 `main.py`、`work_mode_integration.py`；修改 `tests/test_authorization.py`，新增 `tests/test_nl_dispatch.py`。

**Interfaces:**

- 新增 `ActionRequest(name: str, fields: dict[str, object], source: str)` 数据类；`source` 仅允许 command/rule/llm/confirmation。
- 新增 `authorize_action(plugin, event, action_name: str, astrbot_cfg: dict) -> bool`。
- 新增 `dispatch_action(plugin, event, request: ActionRequest) -> None` 异步入口。
- 每种 action 映射现有 command handler；停用或丢失 handler 一律拒绝；`multica enter` 保留作为工作输入权限锚点。

- [ ] 写回归用例：成员 NL 创建资源、读取被禁收件箱、切全局项目均经过真实映射的过滤器；disabled handler、admin/custom filter 拒绝时业务函数调用数为 0；测试规则和模拟 LLM 两种来源。
- [ ] 写 `test_disabled_bridge_does_not_call_provider`：关闭 enabled、nl_enabled、会话访问或全部可用 action 时，Provider 调用数为 0。
- [ ] 运行目标用例确认旧实现失败；实现统一入口，把 enabled/access 检查移到模型调用前；权限检查失败不能通过直接 `_cmd_*` 旁路。
- [ ] 为 1.0.1 临时拒绝 NL 直接写操作并给明确命令指引；只读 NL 仍经过授权。任务 5 完成后以确认流替代临时限制。
- [ ] 运行 `python -m pytest tests/test_authorization.py tests/test_nl_dispatch.py tests/test_nl.py tests/test_routing.py`；预期全部通过。
- [ ] 审查后提交 `fix: enforce command permissions for natural language actions`。

## Task 2：修复工作区与资源解析

**Files:** 修改 `multica_client.py`、`chat_client.py`、`main.py`、`web_api.py`；修改 `tests/test_core.py`、`tests/test_chat_client.py`、`tests/test_dashboard.py`。

**Interfaces:**

- `_pick_workspace(workspaces)` 保留返回形状；显式未匹配、多工作区无选择时抛出明确 ValueError，所有调用者转换为各自规范错误，不让测试连接假成功。
- 新增 `resolve_unique_resource(value: str, items: list[dict], name_key: str) -> dict`：完整 ID、唯一精确名称、唯一 ID 前缀（>=8 位）；零/多匹配报错并返回可展示候选信息。
- 新增 `apply_context_update(current: dict, patch: dict, workspaces: list[dict], projects: list[dict]) -> dict`：验证项目归属，工作区变化且未明确新项目时清空 project_id，返回待保存配置。

- [ ] 写失败用例：错拼 slug 不回退；空配置单工作区可选；空配置多工作区要求选择；无工作区报错；旧合法 UUID 保持工作。
- [ ] 写失败用例：精确名称可找到项目；重复名称/重复前缀拒绝；找不到的姓名不能冒充 ID。
- [ ] 写失败用例：工作区变化清空旧项目；跨工作区项目拒绝；校验失败磁盘与内存配置均不变。
- [ ] 实现解析和调用者错误转换；确认前和提交前按当前连接重新验证资源归属。
- [ ] 统一相关 HTTP 的 URL 前缀保留和安全错误格式；不把服务器原始错误正文或 Token 回传 QQ。扩展本地 HTTP 测试覆盖工作区自动发现路径。
- [ ] 运行 `python -m pytest tests/test_core.py tests/test_chat_client.py tests/test_dashboard.py tests/test_upgrade.py`；预期全部通过。
- [ ] 审查后提交 `fix: reject ambiguous workspace and resource selection`。

## Task 3：让停止控制优先于旧排队消息

**Files:** 修改 `work_mode.py`、必要时 `chat_client.py`；扩展 `tests/test_races.py`、`tests/test_work_mode.py`。

**Interfaces:**

- WorkMode 新增内存 `submission_epochs: dict[str, int]` 与 `stopping: set[str]`；只控制消息提交，不改变回复 generation 或持久化格式。
- 新增异步 `_stop(event, key: str) -> None`，不排在普通消息提交锁之后。
- 提交捕获 epoch；历史读取后及 POST 前均检查 epoch、active、连接和授权。stop 推进 epoch，让此前等待的消息失效。

- [ ] 写失败用例复刻审查 trace：两条旧消息排队后 stop 不得等待它们全部发送；尚未提交的旧消息数应归零。
- [ ] 写停止期间新消息用例：提示“正在停止，稍后重试”，不悄悄接受；stop 完成后允许新的正常提交。
- [ ] 写在途 POST 用例：成功、明确失败、超时但服务端已接受、服务端未接受；不能在请求尚可能迟到时先取消再宣告已全部停止。
- [ ] 实现停止屏障和在途提交结算；结果不明确时保留 uncertain 并提示待核对，不自动重发；已创建远端任务通过 pending/取消接口处理。
- [ ] 运行 `python -m pytest tests/test_races.py tests/test_work_mode.py tests/test_reply_worker.py`；预期全部通过，并保留退出可立即完成的测试。
- [ ] 审查后提交 `fix: invalidate queued submissions before stopping remote work`。

任务 1–3 及下列安全修复完成后可以准备 1.0.1：只消费一次关键词（任务 4 的独立修复）、更新不实帮助、完整回归。新 NL 功能不必阻塞安全补丁。

## Task 4：结构化 NL 与可靠的模型边界

**Files:** 修改 `nl_control.py`、`main.py`、`actions.py`、`work_mode.py`、`work_mode_integration.py`；扩展 `tests/test_nl.py`、`tests/test_nl_dispatch.py`、`tests/test_work_mode.py`；新增 `tests/test_nl_provider.py`。

**Interfaces:**

- 新增 `ParseResult(status: str, request: ActionRequest | None, question: str)`；status 仅 executable/clarify/ignore。
- 新增 `parse_control_request(text: str, keyword: str, now) -> ParseResult`，保留旧 parser 作兼容适配直到调用者迁移完毕。
- 新增 `parse_work_enter(text: str, keyword: str) -> ParseResult`，先在原始消息上识别明确的进入/切换句式，再运行普通管理意图的调用前缀规则；支持关键词在句中/句尾及“工作”省略“模式”，不全局替换正文。
- 新增 `validate_action_fields(action: str, fields: dict, now) -> dict`：白名单字段、严格类型、优先级/状态枚举、数量 1–50、真实日期。
- 模型协议为 `{"action":"…","fields":{…}}`，只允许五种 NL action，其中 `work_enter` 的 fields 必须为空对象；需要澄清时返回 `{"action":"none","fields":{}}`，由本地原文与校验给出澄清信息。不接受 args 字符串、任意 action 或额外执行代码。
- WorkMode 新增异步 `enter_from_intent(event) -> None`，与 `/multica` 共享授权后的进入/恢复流程；不改写原消息正文，不跳过当前安全守卫，不把任务文本与进入动作一起提交。事件完成后终止传播，普通失败不会由默认模型继续处理同一条控制消息。

- [ ] 写原文保真用例：正文含 multica、不同大小写、notmultica、引用中的关键词、带礼貌前缀的真实调用。
- [ ] 写语义用例：否定、暂不执行、操作教学、条件句、两个动作、裸“退出”、缺标题；断言不产生写 API 请求。
- [ ] 写自然语言进入用例：规则和模拟 LLM 输出 work_enter 均能进入；禁用 enter、成员无权限、名单拒绝、工作转发关闭或路由不兼容时均不得创建 Chat；多智能体未选择时只列候选；“不要进入/怎么进入”不进入；“进入后顺便执行任务”先澄清且不提交任务。
- [ ] 参数化验证明确口语均由规则识别为 work_enter，fields 为 `{}`，且 Provider 调用数为 0：“进入multica模式”“进入 multica 工作模式”“切换为multica工作”“切换到 Multica 工作模式”“切到multica模式”“转到multica工作模式”“multica，进入工作模式”“帮我进入 multica 工作模式”；补大小写和中英文相邻空格变体。
- [ ] 参数化验证“不要进入multica模式”“怎么切换为multica工作”“他说进入multica模式”“如果进入multica模式会怎样”、裸 multica 和“开始工作”均不进入；模拟 LLM 对这些否定/教学/引用语句输出 work_enter 时，本地语义校验仍拒绝自动进入。
- [ ] 写路由用例：进入成功后后续文字交给 Multica，已在工作模式时不重复运行普通 NL，也不因再次提到进入/退出而改变状态；退出仍使用 `/multica exit`。
- [ ] 写字段用例：最近5条/五条、明天/下周的歧义、闰年、2026-02-31、错误类型、未知字段、非法 action、提示注入；不能悄悄丢字段或编造 ID。
- [ ] 将规则与 LLM 统一为结构化字段；规则仅可靠单动作命中，歧义进入澄清；规则命中不能免除参数验证。
- [ ] Provider 调用加 10 秒 timeout、同窗口并发 1、同用户 5 秒调用间隔，不重试；注入时区和本地日期；旧签名兼容不能因内部 TypeError 再发第二次请求。
- [ ] 模拟 Provider 验证：无模型、超时、错误 JSON、模型建议越权操作、旧签名、重复消息；确保错误文本和凭据不进入用户可见回复。
- [ ] 运行 `python -m pytest tests/test_nl.py tests/test_nl_dispatch.py tests/test_nl_provider.py tests/test_work_mode.py tests/test_authorization.py`；预期全部通过。
- [ ] 审查后提交 `feat: validate structured natural language requests`。

## Task 5：NL 写操作草稿、确认与防重复

**Files:** 新建 `pending_intents.py`；修改 `main.py`、`actions.py`；新增 `tests/test_nl_confirmation.py`。

**Interfaces:**

- 新增 `PendingIntentStore.create(owner: tuple[str, ...], request: ActionRequest, context_key: str, now: float) -> str`，生成 6 位短码并存入 120 秒内存草稿。
- 新增 `claim(owner: tuple[str, ...], code: str, context_key: str, now: float) -> ActionRequest | None`，一次性领取；`cancel(owner, code) -> bool`。
- owner 包含平台实例、自身账号、聊天窗口和发起人；context_key 包含连接指纹、当前 Chat ID 与 generation。确认时重新授权和校验，不能只依赖草稿创建时的权限。

- [ ] 写草稿用例：NL 创建仅显示预览；写 API 调用数为 0；预览包含目标工作区、项目和最终字段。
- [ ] 写确认用例：本人短码可以提交一次；不同群/不同成员/过期/错误短码/重复确认均不提交。
- [ ] 写上下文用例：改 Token、换工作区/项目、换 Chat、退出、停用命令或降低权限后确认旧草稿均失效。
- [ ] 写超时用例：创建结果不明确时提示核对并消费短码，不自动重试，不能再次确认造成重复 Issue。
- [ ] 实现草稿、取消和确认入口；只匹配完整 `确认 <短码>` / `取消 <短码>`；工作模式普通文字不由该入口拦截。
- [ ] 运行 `python -m pytest tests/test_nl_confirmation.py tests/test_nl_dispatch.py tests/test_authorization.py`；预期全部通过。
- [ ] 审查后提交 `feat: require owner confirmation for natural language writes`。

## Task 6：命令展示、WebUI 和兼容迁移

**Files:** 修改 `main.py`、`work_mode.py`、`web_api.py`、`pages/settings/index.html`、两份 `.astrbot-plugin/i18n/*.json`；修改命令、页面及浏览器测试。

**Interfaces:**

- `actions.py` 增加统一命令描述数据：主菜单 7 项，高级 Issue/inbox 2 项，兼容 enter 与 workspace/project 六项；保留原 handler 标识和权限映射。
- Web API 新增只读工作区/项目选项接口，返回 id、name/title、workspace_id 和当前选中值，不返回凭据。
- `agent` 无参数改为只列候选；有有效选择才创建 Chat。

- [ ] 写命令展示用例：主帮助恰有 7 项，exit/new/agent/stop/status/help 均为 multica 子命令；`/multica` 重复调用保持进入/恢复语义，不自动退出；advanced 显示 Issue/inbox；旧 handler 和别名仍可解析并经过任务 1 授权。
- [ ] 写迁移用例：旧 workspace/project 管理命令先说明影响范围及 WebUI 入口；旧 NL 管理请求只给迁移指引，不调用修改 API。
- [ ] 页面加入工作区/项目选择并使用任务 2 的配置校验；连接改变时显示受影响会话，要求 `/multica new`；不新增按群配置体系。
- [ ] 把普通帮助、工作帮助、WebUI、README 的命令及能力边界统一；收件箱准确标注“最新创建 50 条窗口”，不宣称全工作区最近更新。
- [ ] 减少快速成功回执；2 秒内收到结果不重复回执，超过 2 秒或排队/失败时保留提示；补时间控制测试。
- [ ] 浏览器测试覆盖工作区切换清项目、失败不保存、保存竞态、刷新持久化、手机、双语和主题；保持现有风格。
- [ ] 运行 `python -m pytest tests/test_commands.py tests/test_dashboard.py tests/test_upgrade.py tests/test_races.py` 及现有浏览器脚本；预期通过且页面无控制台错误、无横向溢出。
- [ ] 审查后提交 `feat: simplify work commands and move global management to settings`。

## Task 7：全量验证、文档和发布准备

**Files:** 更新 `README.md`、`CHANGELOG.md`、`metadata.yaml`、验证记录、CI；按引用检查结果清理资源；沿用 `scripts/build_package.py`。

- [ ] 加入必要的结构化诊断：阶段、异常类型、HTTP 状态、耗时、提交是否不确定；不记录 Token 或完整消息。异常不能只给通用提示而不留诊断日志。
- [ ] 清查静态资源引用，确认页面、README 和安装包均不依赖后再删除；只格式化本轮改动文件，不把格式差异混成大规模重写。
- [ ] Python 3.10/3.12 各跑完整 pytest；`REQUIRE_UPSTREAM_TESTS=1`，两个上游集成用例必须执行，不能用 skip 代替通过。
- [ ] 运行 `python -m ruff check .` 与 `python -m ruff format --check .`；运行打包脚本，检查 ZIP 不含 .validation、测试凭据或草稿，做旧版覆盖升级与备份回滚测试。
- [ ] 浏览器验收沿用 `tests/browser/serve.py`、`check.cjs` 和 `races.cjs`，启动服务与客户端使用独立终端，保留截图和结果。
- [ ] 在获准的真实环境验证：群 A 连续对话、群 B/私聊隔离、普通成员权限、stop 排队、exit、重载、不同智能体；区分本地模拟和线上结果。
- [ ] 真 Provider 用至少 40 条固定语料评测：正向单动作 12、只读 6、否定/教学/引用 6、复合/缺字段 6、资源/日期歧义 6、恶意/非法输出 4；保存模型标识与版本、输入、预期路由和实际动作。不调用用户真实业务写入，使用隔离测试资源；模型调用可能产生费用。
- [ ] 验收禁止行为全部为 0：未授权写入、未经确认写入、跨工作区误写、错误确认写入、停用后解析、stop 后旧队列提交。没有真环境时将对应项明确标为未验证，不能据此宣布发布验收通过。
- [ ] 更新版本和变更日志，生成安装 ZIP、SHA256、升级和回滚说明；用户后续要求发布时再执行 main 推送、标签、Release 和远程产物验证。

## 交付顺序与工作量判断

1. 先完成安全补丁：任务 1、2、3 及任务 4 中关键词保真修复，补文档和回归。
2. 再完成结构化 NL 和确认：任务 4、5，独立验证无误写。
3. 最后调整命令/WebUI，完成任务 6、7。

主要工作量在统一授权、停止竞态和确认状态，收起帮助菜单本身成本较低。不依赖新平台，不扩展多模态，不新增自动 Agent 调度，不承诺未经联调的服务端工具能力。

任务 1 → 2 → 3 优先顺序执行；4 依赖 1/2，5 依赖 4，6 依赖前述最终接口，7 为整体交付门槛。用户评审两份文档后可选择一次完整更新，或先交付 1.0.1 安全补丁。
