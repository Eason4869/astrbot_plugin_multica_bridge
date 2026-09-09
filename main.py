"""Multica 桥接插件主入口。

将 AstrBot 接入 Multica 平台：连接测试、通过聊天指令创建 Issue、管理工作区与项目。
所有配置通过 WebUI 设置页管理，修改后自动保存热生效。

指令使用 AstrBot 标准的指令组（``@filter.command_group``）注册，
因此每条子指令在 AstrBot「指令管理」中都是独立条目，
可分别设置「仅管理员 / 成员可」等权限。
"""

from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Any, Callable, Coroutine

from astrbot import logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.star import Context, Star
from astrbot.core.message.components import Plain
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

from .web_api import WebApiMixin

_STATUS_ICONS = {
    "todo": "🔴",
    "in_progress": "🟡",
    "in_review": "🔵",
    "backlog": "⚪",
    "done": "🟢",
    "cancelled": "⚫",
}

_PRIORITY_LABELS = {
    "urgent": "紧急",
    "high": "高",
    "medium": "中",
    "low": "低",
}

# 中文优先级 -> API 值，便于用户直接用中文输入
_PRIORITY_ALIASES = {v: k for k, v in _PRIORITY_LABELS.items()}

_ASSIGNEE_LABELS = {
    "agent": "智能体",
    "squad": "团队",
    "member": "成员",
}

_VALID_STATUS = (
    "backlog",
    "todo",
    "in_progress",
    "in_review",
    "done",
    "cancelled",
)


class Main(WebApiMixin, Star):
    """Multica 桥接插件入口。

    继承 WebApiMixin 注册 REST API（/config、/actions/save_config、
    /actions/test_connection），Star 提供 AstrBot 运行时能力。
    """

    def __init__(self, context: Context, config: dict | None = None) -> None:
        super().__init__(context)
        self.context = context
        self.config = config or {}
        # Star 基类会注入插件级 logger；缺失时回退到全局 logger
        self.log = getattr(self, "logger", None) or logger

    async def initialize(self) -> None:
        """插件加载时初始化：构建运行时配置 + 注册 Web API。"""
        try:
            from .config import CONFIG_DEFAULTS, deep_merge, load_plugin_config

            # AstrBot Star 基类不提供 get_data_dir()，使用官方工具函数获取插件数据目录
            data_dir = str(Path(get_astrbot_data_path()) / "plugin_data" / self.name)
            self._data_dir = data_dir
            self.cfg = deep_merge(
                CONFIG_DEFAULTS,
                load_plugin_config(data_dir),
            )
        except Exception as e:
            self.log.warning("[multica_bridge] 加载配置失败，使用默认值: %s", e)
            from .config import CONFIG_DEFAULTS

            self.cfg = dict(CONFIG_DEFAULTS)

        try:
            self.register_routes()
        except Exception as e:
            self.log.warning("[multica_bridge] Web API 注册失败: %s", e)

    # ── 指令组：/multica ──
    #
    # 结构（在 AstrBot 指令管理中同样是树形展示，可逐条设置权限）：
    #   multica
    #   ├── help / status / inbox
    #   ├── issue    -> create
    #   ├── workspace-> list / select / create
    #   └── project  -> list / select / create
    # 不输入子指令时（如直接发送 /multica），AstrBot 会自动渲染指令树。

    @filter.command_group("multica")
    def multica(self) -> None:
        """Multica 桥接指令组。"""

    @multica.command("help", alias={"帮助", "h"})
    async def multica_help(self, event: AstrMessageEvent) -> None:
        """显示 Multica 桥接指令帮助。"""
        await self._run(event, partial(self._cmd_help, event))

    @multica.command("status", alias={"状态"})
    async def multica_status(self, event: AstrMessageEvent) -> None:
        """检查 Multica 连接与当前工作区/项目状态。"""
        await self._run(event, partial(self._cmd_status, event))

    @multica.command("inbox", alias={"收件箱"})
    async def multica_inbox(self, event: AstrMessageEvent) -> None:
        """查看收件箱：最近 Issue 及进展。"""
        await self._run(
            event,
            partial(self._cmd_inbox, event, self._args(event, 2)),
        )

    @multica.group("issue", alias={"议题"})
    def multica_issue(self) -> None:
        """Issue 相关指令组。"""

    @multica_issue.command("create", alias={"新建"})
    async def multica_issue_create(self, event: AstrMessageEvent) -> None:
        """新建 Issue（支持 --desc/--priority/--status/--assignee 等）。"""
        await self._run(
            event,
            partial(self._cmd_issue_create, event, self._args(event, 3)),
        )

    @multica.group("workspace", alias={"工作区"})
    def multica_workspace(self) -> None:
        """工作区相关指令组。"""

    @multica_workspace.command("list", alias={"列表"})
    async def multica_workspace_list(self, event: AstrMessageEvent) -> None:
        """列出当前 Token 可访问的所有工作区。"""
        await self._run(event, partial(self._cmd_workspace_list, event))

    @multica_workspace.command("select", alias={"选择", "切换"})
    async def multica_workspace_select(self, event: AstrMessageEvent) -> None:
        """切换当前工作区（持久化）。"""
        await self._run(
            event,
            partial(self._cmd_workspace_select, event, self._args(event, 3)),
        )

    @multica_workspace.command("create", alias={"新建"})
    async def multica_workspace_create(self, event: AstrMessageEvent) -> None:
        """创建工作区。"""
        await self._run(
            event,
            partial(self._cmd_workspace_create, event, self._args(event, 3)),
        )

    @multica.group("project", alias={"项目"})
    def multica_project(self) -> None:
        """项目相关指令组。"""

    @multica_project.command("list", alias={"列表"})
    async def multica_project_list(self, event: AstrMessageEvent) -> None:
        """列出当前工作区下的所有项目。"""
        await self._run(event, partial(self._cmd_project_list, event))

    @multica_project.command("select", alias={"选择", "切换"})
    async def multica_project_select(self, event: AstrMessageEvent) -> None:
        """切换当前项目（持久化）。"""
        await self._run(
            event,
            partial(self._cmd_project_select, event, self._args(event, 3)),
        )

    @multica_project.command("create", alias={"新建"})
    async def multica_project_create(self, event: AstrMessageEvent) -> None:
        """创建项目。"""
        await self._run(
            event,
            partial(self._cmd_project_create, event, self._args(event, 3)),
        )

    # ── 统一入口守卫 ──

    async def _run(
        self,
        event: AstrMessageEvent,
        action: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        """统一守卫：启用检查 → 会话过滤 → 执行 → 终止事件传播。

        - 插件停用时给出明确提示，并终止事件（不再交给 LLM）。
        - 会话被黑白名单过滤时不终止事件，交回 LLM 处理（与历史行为一致）。
        """
        try:
            cfg = getattr(self, "cfg", None) or {}
            if not cfg.get("enabled", True):
                await self._reply(
                    event,
                    "⛔ Multica 桥接当前已停用。请在 AstrBot WebUI → 插件 → "
                    "Multica桥接 → 设置 中启用后再试。",
                )
                event.stop_event()
                return

            if not self._chat_allowed(event):
                return

            await action()
        except Exception as e:
            self.log.error("[multica_bridge] 指令处理异常: %s", e)
        event.stop_event()

    def _chat_allowed(self, event: AstrMessageEvent) -> bool:
        """按黑白名单配置判断当前会话是否允许执行指令。"""
        from .multica_client import check_chat_allowed

        chat_type = "group" if self._is_group_chat(event) else "private"
        chat_id = self._get_chat_id(event)
        cfg = getattr(self, "cfg", None) or {}
        if chat_id and not check_chat_allowed(cfg, chat_type, chat_id):
            self.log.debug(
                "[multica_bridge] 会话 %s (%s) 被过滤配置拦截",
                chat_id,
                chat_type,
            )
            return False
        return True

    @staticmethod
    def _args(event: AstrMessageEvent, tokens: int) -> str:
        """取指令词之后的剩余参数文本。

        AstrBot 只剥离唤醒前缀（如 ``/``），``event.message_str`` 仍保留
        ``multica workspace create ...`` 全文。这里按空白切分并丢弃前
        ``tokens`` 个指令词，从而同时兼容别名写法。
        """
        text = (event.message_str or "").strip()
        parts = text.split(maxsplit=tokens)
        return parts[tokens].strip() if len(parts) > tokens else ""

    @staticmethod
    def _parse_flags(args: str, flags: tuple[str, ...]) -> tuple[str, dict[str, str]]:
        """把 ``标题 --desc 描述 --slug s`` 解析为 ``(标题, {"--desc": ...})``。

        未出现的 flag 不会出现在结果中；重复出现的 flag 以第一次为准。
        """
        parts = (args or "").split()
        positions = sorted((parts.index(f), f) for f in flags if f in parts)
        if not positions:
            return " ".join(parts).strip(), {}

        head = " ".join(parts[: positions[0][0]]).strip()
        values: dict[str, str] = {}
        for i, (idx, flag) in enumerate(positions):
            end = positions[i + 1][0] if i + 1 < len(positions) else len(parts)
            values[flag] = " ".join(parts[idx + 1 : end]).strip()
        return head, values

    # ── 通用工具 ──

    @staticmethod
    def _get_chat_id(event: AstrMessageEvent) -> str:
        """从事件中提取会话 ID（群号或用户号）。"""
        group_id = event.get_group_id()
        if group_id:
            return group_id
        sender_id = event.get_sender_id()
        if sender_id:
            return sender_id
        return ""

    @staticmethod
    def _is_group_chat(event: AstrMessageEvent) -> bool:
        return not event.is_private_chat()

    @staticmethod
    def _slugify(name: str) -> str:
        """按名称自动生成 slug：仅保留字母/数字/空格，空格转连字符，转小写。"""
        import re

        cleaned = re.sub(r"[^a-zA-Z0-9 ]", "", name).strip().lower()
        return re.sub(r"\s+", "-", cleaned)

    def _save_cfg(self) -> None:
        """将当前 self.cfg 原子写入插件自有 config.json。"""
        try:
            from .config import save_plugin_config

            data_dir = getattr(self, "_data_dir", None) or str(
                Path(get_astrbot_data_path()) / "plugin_data" / self.name
            )
            save_plugin_config(data_dir, self.cfg)
        except Exception as e:
            self.log.error("[multica_bridge] 保存配置失败: %s", e)
            raise

    # ── 子指令实现 ──

    async def _cmd_help(self, event: AstrMessageEvent) -> None:
        help_text = (
            "Multica 桥接插件命令：\n"
            "/multica — 显示指令树（不输子指令时）\n"
            "/multica help — 显示此帮助\n"
            "/multica status — 检查连接、当前工作区与项目\n"
            "/multica issue create <标题> [选项] — 新建 Issue\n"
            "   选项：--desc 描述 --priority 紧急|高|中|低\n"
            "         --status todo|in_progress|in_review|backlog|done\n"
            "         --assignee <id> --project <id> --due YYYY-MM-DD\n"
            "         --labels 标签1,标签2\n"
            "/multica workspace list — 列出可访问的工作区\n"
            "/multica workspace select <id|slug> — 切换当前工作区（持久化）\n"
            "/multica workspace create <名称> [--slug slug] [--desc 描述] [--context 背景]\n"
            "/multica project list — 列出当前工作区的项目\n"
            "/multica project select <id> — 切换当前项目（持久化）\n"
            "/multica project create <标题> [--desc 描述] — 创建项目\n"
            "/multica inbox [数量] [open|done] — 查看收件箱（最近 Issue 及进展）"
        )
        await self._reply(event, help_text)

    async def _cmd_status(self, event: AstrMessageEvent) -> None:
        from .multica_client import MulticaClient, mask_secret

        client = MulticaClient(self.cfg)
        result = await client.test_connection()
        if not result["ok"]:
            await self._reply(event, f"❌ Multica 连接失败：{result['message']}")
            return

        lines = ["✅ Multica 连接正常"]
        name = result.get("workspace_name")
        wsid = result.get("workspace_id")
        slug = result.get("workspace_slug")
        if name:
            detail = f"• 工作区：{name}"
            if slug:
                detail += f"（slug: {slug}）"
            lines.append(detail)
            if wsid:
                lines.append(f"  id: {wsid}")

        project_id = str(self.cfg.get("project_id") or "").strip()
        if project_id:
            title = await client.get_project_title(project_id)
            lines.append(
                f"• 项目：{title}（{project_id}）"
                if title
                else f"• 项目 id：{project_id}（未能解析标题）"
            )
        else:
            lines.append("• 项目：未指定（新建 Issue 将进入工作区默认项目）")

        token = str(self.cfg.get("token") or "")
        lines.append(f"• Token：{mask_secret(token)}")
        lines.append(f"• API：{self.cfg.get('api_url') or '（未配置）'}")
        await self._reply(event, "\n".join(lines))

    async def _cmd_issue_create(self, event: AstrMessageEvent, args: str) -> None:
        """处理 ``/multica issue create``：通过 HTTP API 创建 Issue。

        不依赖本机是否安装 multica CLI，避免“本机未安装 multica”误报。
        """
        from .multica_client import MulticaClient

        flags = (
            "--desc",
            "--priority",
            "--status",
            "--assignee",
            "--project",
            "--due",
            "--labels",
        )
        title, values = self._parse_flags(args, flags)

        if not title:
            await self._reply(
                event,
                "用法：/multica issue create <标题> [--desc 描述] [--priority 紧急|高|中|低]\n"
                "示例：/multica issue create 修复登录失败 --desc 用户反馈登录超时 --priority 高",
            )
            return

        missing = [f for f in flags if f in values and not values[f]]
        if missing:
            await self._reply(event, f"❌ 参数 {missing[0]} 缺少值")
            return

        priority = values.get("--priority", "").strip()
        priority = _PRIORITY_ALIASES.get(priority, priority)
        status = values.get("--status", "").strip()
        if status and status not in _VALID_STATUS:
            await self._reply(
                event,
                f"❌ 无效的 --status：{status}\n"
                f"可选：{'、'.join(_VALID_STATUS)}",
            )
            return

        labels = [
            s.strip()
            for s in values.get("--labels", "").replace("，", ",").split(",")
            if s.strip()
        ]

        client = MulticaClient(self.cfg)
        result = await client.create_issue(
            title=title,
            description=values.get("--desc", ""),
            priority=priority,
            status=status,
            assignee_id=values.get("--assignee", "").strip(),
            project_id=values.get("--project", "").strip(),
            due_date=values.get("--due", "").strip(),
            labels=labels,
        )
        if result["ok"]:
            await self._reply(event, f"✅ {result['message']}")
        else:
            await self._reply(event, f"❌ 创建失败：{result['message']}")

    async def _cmd_workspace_list(self, event: AstrMessageEvent) -> None:
        """列出当前 Token 可访问的所有工作区。"""
        from .multica_client import MulticaClient

        client = MulticaClient(self.cfg)
        result = await client.list_workspaces()
        if not result["ok"]:
            await self._reply(event, f"❌ 获取工作区失败：{result['message']}")
            return

        workspaces = result["workspaces"]
        current = (self.cfg.get("workspace_id") or "").strip().lower()
        lines = [f"共 {len(workspaces)} 个工作区："]
        for ws in workspaces:
            if not isinstance(ws, dict):
                continue
            name = ws.get("name") or "（未命名）"
            slug = ws.get("slug") or ""
            wsid = ws.get("id") or ""
            marker = " ✓" if wsid and str(wsid).lower() == current else ""
            lines.append(f"• {name}（slug: {slug}）{marker}\n  {wsid}")
        lines.append("发送 /multica workspace select <id|slug> 可切换当前工作区")
        await self._reply(event, "\n".join(lines))

    async def _cmd_workspace_select(self, event: AstrMessageEvent, target: str) -> None:
        """切换当前工作区并持久化到插件自有 config.json。"""
        from .multica_client import MulticaClient

        target = (target or "").strip()
        if not target:
            await self._reply(
                event,
                "用法：/multica workspace select <id|slug>\n"
                "示例：/multica workspace select eason-service",
            )
            return

        client = MulticaClient(self.cfg)
        result = await client.list_workspaces()
        if not result["ok"]:
            await self._reply(event, f"❌ 获取工作区失败：{result['message']}")
            return

        ws = client.find_workspace(target, result["workspaces"])
        if ws is None:
            await self._reply(
                event,
                f"❌ 未找到工作区 {target}。可用列表请查看 /multica workspace list",
            )
            return

        wsid = str(ws.get("id") or "").strip()
        name = ws.get("name") or "（未命名）"
        if not wsid:
            await self._reply(event, "❌ 目标工作区缺少 id，无法切换")
            return

        self.cfg["workspace_id"] = wsid
        self._save_cfg()
        await self._reply(
            event,
            f"✅ 已切换到工作区 {name}（{wsid}）\n"
            "该选择已持久化，重启后仍然生效。",
        )

    async def _cmd_workspace_create(self, event: AstrMessageEvent, args: str) -> None:
        """创建工作区（name 必填，slug 缺省时按名称自动生成）。"""
        from .multica_client import MulticaClient

        flags = ("--slug", "--desc", "--context")
        name, values = self._parse_flags(args, flags)
        if not (args or "").strip():
            await self._reply(
                event,
                "用法：/multica workspace create <名称> [--slug slug] "
                "[--desc 描述] [--context 背景信息]\n"
                "示例：/multica workspace create 项目A --slug project-a --desc 测试环境",
            )
            return

        missing = [f for f in flags if f in values and not values[f]]
        if missing:
            await self._reply(event, f"❌ 参数 {missing[0]} 缺少值")
            return

        if not name:
            await self._reply(event, "❌ 工作区名称不能为空")
            return

        slug = values.get("--slug", "").strip()
        if not slug:
            slug = self._slugify(name)
        if not slug:
            await self._reply(
                event,
                "❌ 无法从名称自动生成 slug，请使用 --slug 指定"
                "（仅允许小写字母、数字和连字符）",
            )
            return

        client = MulticaClient(self.cfg)
        result = await client.create_workspace(
            name=name,
            slug=slug,
            description=values.get("--desc", ""),
            context=values.get("--context", ""),
        )
        if result["ok"]:
            await self._reply(event, f"✅ {result['message']}")
        else:
            await self._reply(event, f"❌ 创建失败：{result['message']}")

    async def _cmd_project_list(self, event: AstrMessageEvent) -> None:
        """列出当前工作区下的所有项目。"""
        from .multica_client import MulticaClient

        client = MulticaClient(self.cfg)
        result = await client.list_projects()
        if not result["ok"]:
            await self._reply(event, f"❌ 获取项目列表失败：{result['message']}")
            return

        projects = result.get("projects") or []
        current = (self.cfg.get("project_id") or "").strip().lower()
        lines = [f"共 {len(projects)} 个项目："]
        for proj in projects:
            if not isinstance(proj, dict):
                continue
            title = proj.get("title") or "（未命名）"
            pid = proj.get("id") or ""
            marker = " ✓" if pid and str(pid).lower() == current else ""
            lines.append(f"• {title}{marker}\n  {pid}")
        lines.append("发送 /multica project select <id> 可切换当前项目")
        await self._reply(event, "\n".join(lines))

    async def _cmd_project_select(self, event: AstrMessageEvent, target: str) -> None:
        """切换当前项目并持久化到插件自有 config.json。"""
        from .multica_client import MulticaClient

        target = (target or "").strip()
        if not target:
            await self._reply(
                event,
                "用法：/multica project select <id>\n"
                "示例：/multica project select e8a339ad-32ec-49ac-bbd7-0c8d7e1b1466",
            )
            return

        client = MulticaClient(self.cfg)
        result = await client.list_projects()
        if not result["ok"]:
            await self._reply(event, f"❌ 获取项目列表失败：{result['message']}")
            return

        proj = client.find_project(target, result.get("projects") or [])
        if proj is None:
            await self._reply(
                event,
                f"❌ 未找到项目 {target}。可用列表请查看 /multica project list",
            )
            return

        pid = str(proj.get("id") or "").strip()
        title = proj.get("title") or "（未命名）"
        if not pid:
            await self._reply(event, "❌ 目标项目缺少 id，无法切换")
            return

        self.cfg["project_id"] = pid
        self._save_cfg()
        await self._reply(
            event,
            f"✅ 已切换到项目 {title}（{pid}）\n"
            "该选择已持久化，重启后仍然生效。",
        )

    async def _cmd_project_create(self, event: AstrMessageEvent, args: str) -> None:
        """创建项目（title 必填，--desc 为可选描述）。"""
        from .multica_client import MulticaClient

        flags = ("--desc",)
        title, values = self._parse_flags(args, flags)
        if not (args or "").strip():
            await self._reply(
                event,
                "用法：/multica project create <标题> [--desc 描述]\n"
                "示例：/multica project create 前端重构 --desc 计划中的前端重构项目",
            )
            return

        if not title:
            await self._reply(event, "❌ 项目标题不能为空")
            return

        client = MulticaClient(self.cfg)
        result = await client.create_project(
            title=title,
            description=values.get("--desc", ""),
        )
        if result["ok"]:
            await self._reply(event, f"✅ {result['message']}")
        else:
            await self._reply(event, f"❌ 创建失败：{result['message']}")

    async def _cmd_inbox(self, event: AstrMessageEvent, args: str) -> None:
        """处理 /multica inbox 子命令：展示最近 Issue 与进展。"""
        tokens = args.split()
        status_filter = ""  # "" 全部 / "open" 未完成 / "done" 已完成
        count = 10
        for tok in tokens:
            if tok in ("open", "进行中"):
                status_filter = "open"
            elif tok in ("done", "已完成"):
                status_filter = "done"
            elif tok.isdigit():
                count = max(1, min(int(tok), 50))
            else:
                await self._reply(
                    event,
                    "用法：/multica inbox [数量] [open|done]\n"
                    "示例：/multica inbox 10、/multica inbox open、/multica inbox done 10",
                )
                return

        from .multica_client import MulticaClient

        client = MulticaClient(self.cfg)
        # API 不支持按 updated_at 排序，拉取较新窗口后在本地方完成排序与截断
        result = await client.list_issues(limit=50)
        if not result["ok"]:
            await self._reply(event, f"❌ 获取收件箱失败：{result['message']}")
            return

        issues = result.get("issues") or []
        if status_filter == "open":
            issues = [
                i for i in issues
                if (i.get("status") or "") not in ("done", "cancelled")
            ]
        elif status_filter == "done":
            issues = [
                i for i in issues
                if (i.get("status") or "") in ("done", "cancelled")
            ]

        issues.sort(key=lambda i: i.get("updated_at") or "", reverse=True)
        issues = issues[:count]

        if not issues:
            empty_msg = {
                "": "当前收件箱为空",
                "open": "当前没有未完成的 Issue",
                "done": "当前没有已完成的 Issue",
            }[status_filter]
            await self._reply(event, f"📭 {empty_msg}")
            return

        # 只为当前展示的 Issue 解析指派人名称，避免多余请求
        assignee_ids = {
            str(i.get("assignee_id"))
            for i in issues
            if i.get("assignee_id")
        }
        names = await client.resolve_assignee_names(assignee_ids)

        head = f"📥 Multica 收件箱（最近 {len(issues)} 条"
        if status_filter == "open":
            head += " · 未完成"
        elif status_filter == "done":
            head += " · 已完成/已取消"
        head += "）"
        lines = [self._format_issue(i, names) for i in issues]
        await self._reply(event, head + "\n" + "\n".join(lines))

    @staticmethod
    def _format_issue(issue: dict, names: dict | None = None) -> str:
        """把单条 Issue 压缩为一行：状态图标 + 编号 + 标题 + 优先级 + 指派人。"""
        status = str(issue.get("status") or "")
        icon = _STATUS_ICONS.get(status, "🔘")
        ident = str(issue.get("identifier") or issue.get("id") or "?")
        title = " ".join(str(issue.get("title") or "").split())
        if len(title) > 40:
            title = title[:39] + "…"

        line = f"{icon} {ident} {title}"
        prio = str(issue.get("priority") or "")
        if prio and prio != "none":
            line += f" [{_PRIORITY_LABELS.get(prio, prio)}]"
        assignee_id = issue.get("assignee_id")
        if assignee_id:
            name = (names or {}).get(str(assignee_id))
            if not name:
                atype = str(issue.get("assignee_type") or "")
                name = _ASSIGNEE_LABELS.get(atype, atype) or None
            if name:
                line += f" ({name})"
        return line

    async def _reply(self, event: AstrMessageEvent, text: str) -> None:
        """向消息来源回复。"""
        try:
            await event.send(MessageChain([Plain(text)]))
        except Exception as e:
            self.log.warning("[multica_bridge] 回复消息失败: %s", e)
