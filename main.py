"""Multica 桥接插件主入口。

将 AstrBot 接入 Multica 平台：连接测试、通过聊天指令创建 Issue、管理工作区与项目。
所有配置通过 WebUI 设置页管理，修改后自动保存热生效。
"""

from __future__ import annotations

from pathlib import Path

from astrbot import logger
from astrbot.api.event import AstrMessageEvent, MessageChain
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

_ASSIGNEE_LABELS = {
    "agent": "智能体",
    "squad": "团队",
    "member": "成员",
}


class Main(WebApiMixin, Star):
    """Multica 桥接插件入口。

    继承 WebApiMixin 注册 REST API（/config、/actions/save_config、
    /actions/test_connection），Star 提供 AstrBot 运行时能力。
    """

    def __init__(self, context: Context, config: dict | None = None) -> None:
        super().__init__(context)
        self.context = context
        self.config = config or {}

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
            logger.warning("[multica_bridge] 加载配置失败，使用默认值: %s", e)
            from .config import CONFIG_DEFAULTS

            self.cfg = dict(CONFIG_DEFAULTS)

        try:
            self.register_routes()
        except Exception as e:
            logger.warning("[multica_bridge] Web API 注册失败: %s", e)

        # 注册命令监听（兼容 AstrBot v4.27.2+，使用 StarHandler 体系）
        try:
            from astrbot.core.star.star_handler import (
                EventType,
                StarHandlerMetadata,
                star_handlers_registry,
            )
            from astrbot.core.star.filter.command import CommandFilter

            handler_md = StarHandlerMetadata(
                event_type=EventType.AdapterMessageEvent,
                handler_full_name=f"{self._on_command.__module__}_{self._on_command.__name__}",
                handler_name="_on_command",
                handler_module_path=self._on_command.__module__,
                handler=self._on_command,
                event_filters=[],
                desc="Multica 桥接指令处理",
            )
            handler_md.event_filters.append(
                CommandFilter(command_name="multica", handler_md=handler_md)
            )
            star_handlers_registry.append(handler_md)
        except Exception as e:
            logger.warning("[multica_bridge] 命令监听注册失败: %s", e)

    # ── 命令处理 ──

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

    async def _on_command(self, event: AstrMessageEvent) -> None:
        """处理 /multica 开头的命令。

        通过 StarHandlerMetadata + CommandFilter 注册，确保在 LLM 之前拦截消息。
        """
        try:
            text = (event.message_str or "").strip()

            # CommandFilter 只剥离 / 前缀，text 实际为 "multica <args>"
            # 同时兼容直接调用时保留 /multica 前缀的旧路径
            if text.startswith("/multica"):
                text = text[len("/multica"):].strip()
            elif text.startswith("multica"):
                text = text[len("multica"):].strip()

            # 检查黑/白名单
            from .multica_client import check_chat_allowed

            chat_type = "group" if self._is_group_chat(event) else "private"
            chat_id = self._get_chat_id(event)
            if chat_id and not check_chat_allowed(self.cfg, chat_type, chat_id):
                logger.debug(
                    "[multica_bridge] 会话 %s (%s) 被过滤配置拦截",
                    chat_id, chat_type,
                )
                return

            # 解析子命令（text 已去除前缀，空文本 = help）
            sub = text.split(maxsplit=1)[0].strip() if text else "help"
            args = text[len(sub):].strip() if text else ""

            if sub in ("help", "帮助"):
                await self._cmd_help(event)
            elif sub in ("status", "状态"):
                await self._cmd_status(event)
            elif sub in ("issue", "议题"):
                await self._cmd_issue(event, args)
            elif sub in ("workspace", "工作区"):
                await self._cmd_workspace(event, args)
            elif sub in ("project", "项目"):
                await self._cmd_project(event, args)
            elif sub in ("inbox", "收件箱"):
                await self._cmd_inbox(event, args)
            else:
                await self._reply(event, f"未知子命令: {sub}\n发送 /multica help 查看帮助")

            event.stop_event()  # 阻止 LLM 继续处理此消息
        except Exception as e:
            logger.error("[multica_bridge] 命令处理异常: %s", e)

    async def _cmd_help(self, event: AstrMessageEvent) -> None:
        help_text = (
            "Multica 桥接插件命令：\n"
            "/multica help  — 显示此帮助\n"
            "/multica status — 检查 Multica 连接状态\n"
            "/multica issue create <标题> [--desc 描述] — 新建 Issue\n"
            "/multica workspace list — 列出可访问的工作区\n"
            "/multica workspace select <id|slug> — 切换当前工作区（持久化）\n"
            "/multica workspace create <名称> [--slug slug] [--desc 描述] — 创建工作区\n"
            "/multica project list — 列出当前工作区的项目\n"
            "/multica project select <id> — 切换当前项目（持久化）\n"
            "/multica project create <标题> [--desc 描述] — 创建项目\n"
            "/multica inbox [数量] [open|done] — 查看收件箱（最近 Issue 及进展）"
        )
        await self._reply(event, help_text)

    async def _cmd_status(self, event: AstrMessageEvent) -> None:
        from .multica_client import MulticaClient

        client = MulticaClient(self.cfg)
        result = await client.test_connection()
        if result["ok"]:
            name = result.get("workspace_name")
            await self._reply(event, f"Multica 连接正常{(' — ' + name) if name else ''}")
        else:
            await self._reply(event, f"Multica 连接失败: {result['message']}")

    async def _cmd_issue(self, event: AstrMessageEvent, args: str) -> None:
        """处理 /multica issue 子命令。

        通过 HTTP API 创建 Issue，不依赖本机是否安装 multica CLI
        （避免“本机未安装 multica”误报）。
        """
        from .multica_client import MulticaClient

        parts = args.split()
        if not parts or parts[0] not in ("create", "新建"):
            await self._reply(
                event,
                "用法：/multica issue create <标题> [--desc 描述]\n"
                "示例：/multica issue create 修复登录失败 --desc 用户反馈登录超时",
            )
            return

        # 解析标题与可选描述（--desc 之前为标题）
        tokens = parts[1:]
        desc = ""
        if "--desc" in tokens:
            idx = tokens.index("--desc")
            title = " ".join(tokens[:idx]).strip()
            desc = " ".join(tokens[idx + 1:]).strip()
        else:
            title = " ".join(tokens).strip()

        if not title:
            await self._reply(event, "标题不能为空。用法：/multica issue create <标题>")
            return

        client = MulticaClient(self.cfg)
        result = await client.create_issue(title=title, description=desc)
        if result["ok"]:
            await self._reply(event, f"✅ {result['message']}")
        else:
            await self._reply(event, f"❌ 创建失败：{result['message']}")

    async def _cmd_workspace(self, event: AstrMessageEvent, args: str) -> None:
        """处理 /multica workspace 子命令（list / select / create）。"""
        parts = args.split()
        action = parts[0] if parts else ""
        rest = args[len(action):].strip() if action else ""

        if action in ("list", "列表"):
            await self._cmd_workspace_list(event)
        elif action in ("select", "选择", "切换"):
            await self._cmd_workspace_select(event, rest)
        elif action in ("create", "新建"):
            await self._cmd_workspace_create(event, rest)
        else:
            await self._reply(
                event,
                "用法：\n"
                "/multica workspace list\n"
                "/multica workspace select <id|slug>\n"
                "/multica workspace create <名称> [--slug slug] [--desc 描述]",
            )

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

        parts = (args or "").split()
        if not parts:
            await self._reply(
                event,
                "用法：/multica workspace create <名称> [--slug slug] [--desc 描述]\n"
                "示例：/multica workspace create 项目A --slug project-a --desc 测试环境",
            )
            return

        name = ""
        slug = ""
        desc = ""
        context = ""
        flags = ("--slug", "--desc", "--context")
        flag_indexes = {f: (parts.index(f) if f in parts else -1) for f in flags}
        present = sorted((i, f) for f, i in flag_indexes.items() if i >= 0)
        if present:
            first_flag_idx = present[0][0]
            name = " ".join(parts[:first_flag_idx]).strip()
            for n, (idx, flag) in enumerate(present):
                end = present[n + 1][0] if n + 1 < len(present) else len(parts)
                value = " ".join(parts[idx + 1:end]).strip()
                if not value:
                    await self._reply(event, f"❌ 参数 {flag} 缺少值")
                    return
                if flag == "--slug":
                    slug = value
                elif flag == "--desc":
                    desc = value
                elif flag == "--context":
                    context = value
        else:
            name = " ".join(parts).strip()

        if not name:
            await self._reply(event, "❌ 工作区名称不能为空")
            return

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
            description=desc,
            context=context,
        )
        if result["ok"]:
            await self._reply(event, f"✅ {result['message']}")
        else:
            await self._reply(event, f"❌ 创建失败：{result['message']}")

    async def _cmd_project(self, event: AstrMessageEvent, args: str) -> None:
        """处理 /multica project 子命令（list / select / create）。"""
        parts = args.split()
        action = parts[0] if parts else ""
        rest = args[len(action):].strip() if action else ""

        if action in ("list", "列表"):
            await self._cmd_project_list(event)
        elif action in ("select", "选择", "切换"):
            await self._cmd_project_select(event, rest)
        elif action in ("create", "新建"):
            await self._cmd_project_create(event, rest)
        else:
            await self._reply(
                event,
                "用法：\n"
                "/multica project list\n"
                "/multica project select <id>\n"
                "/multica project create <标题> [--desc 描述]",
            )

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

        parts = (args or "").split()
        if not parts:
            await self._reply(
                event,
                "用法：/multica project create <标题> [--desc 描述]\n"
                "示例：/multica project create 前端重构 --desc 计划中的前端重构项目",
            )
            return

        desc = ""
        if "--desc" in parts:
            idx = parts.index("--desc")
            title = " ".join(parts[:idx]).strip()
            desc = " ".join(parts[idx + 1:]).strip()
        else:
            title = " ".join(parts).strip()

        if not title:
            await self._reply(event, "❌ 项目标题不能为空")
            return

        client = MulticaClient(self.cfg)
        result = await client.create_project(title=title, description=desc)
        if result["ok"]:
            await self._reply(event, f"✅ {result['message']}")
        else:
            await self._reply(event, f"❌ 创建失败：{result['message']}")

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
            logger.error("[multica_bridge] 保存配置失败: %s", e)
            raise

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

        names = await client.resolve_assignee_names()
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

    @staticmethod
    async def _reply(event: AstrMessageEvent, text: str) -> None:
        """向消息来源回复。"""
        try:
            await event.send(MessageChain([Plain(text)]))
        except Exception as e:
            logger.warning("[multica_bridge] 回复消息失败: %s", e)
