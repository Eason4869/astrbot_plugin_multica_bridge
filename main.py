"""Multica 桥接插件主入口。

将 AstrBot 接入 Multica 平台：连接测试、成本报表同步、诊断结果推送。
所有配置通过 WebUI 设置页管理，修改后自动保存热生效。
"""

from __future__ import annotations

from astrbot import logger
from astrbot.api.event import MessageEvent
from astrbot.api.star import Context, Star

from .web_api import WebApiMixin


class Main(WebApiMixin, Star):
    """Multica 桥接插件入口。

    继承 WebApiMixin 注册 REST API（/config、/actions/save_config、
    /actions/test_connection、/actions/sync），Star 提供 AstrBot 运行时能力。
    """

    def __init__(self, context: Context, config: dict | None = None) -> None:
        super().__init__(context)
        self.context = context
        self.config = config or {}

    async def initialize(self) -> None:
        """插件加载时初始化：构建运行时配置 + 注册 Web API。"""
        try:
            from .config import CONFIG_DEFAULTS, deep_merge, load_plugin_config

            data_dir = str(self.get_data_dir())
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

        # 注册命令监听
        try:
            self.context.register_event_listener(
                "on_message",
                self._on_command,
                "multica_bridge",
            )
        except Exception as e:
            logger.warning("[multica_bridge] 命令监听注册失败: %s", e)

    # ── 命令处理 ──

    @staticmethod
    def _get_chat_id(event: MessageEvent) -> str:
        """从事件中提取会话 ID（群号或用户号）。"""
        if hasattr(event, "group_id") and event.group_id:
            return str(event.group_id)
        if hasattr(event, "user_id"):
            return str(event.user_id)
        return ""

    @staticmethod
    def _is_group_chat(event: MessageEvent) -> bool:
        return bool(hasattr(event, "group_id") and getattr(event, "group_id", None))

    async def _on_command(self, event: MessageEvent) -> None:
        """监听所有消息，处理 /multica 开头的命令。"""
        try:
            text = (event.message or "").strip()
            if not text.startswith("/multica"):
                return

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

            # 解析子命令
            parts = text.split(maxsplit=1)
            sub = parts[1].strip() if len(parts) > 1 else "help"

            if sub in ("help", "帮助"):
                await self._cmd_help(event)
            elif sub in ("status", "状态"):
                await self._cmd_status(event)
            elif sub in ("sync", "同步"):
                await self._cmd_sync(event)
            else:
                await self._reply(event, f"未知子命令: {sub}\n发送 /multica help 查看帮助")
        except Exception as e:
            logger.error("[multica_bridge] 命令处理异常: %s", e)

    async def _cmd_help(self, event: MessageEvent) -> None:
        help_text = (
            "Multica 桥接插件命令：\n"
            "/multica help  — 显示此帮助\n"
            "/multica status — 检查 Multica 连接状态\n"
            "/multica sync — 手动触发数据同步"
        )
        await self._reply(event, help_text)

    async def _cmd_status(self, event: MessageEvent) -> None:
        from .multica_client import MulticaClient

        client = MulticaClient(self.cfg)
        result = await client.test_connection()
        if result["ok"]:
            name = result.get("workspace_name")
            await self._reply(event, f"Multica 连接正常{(' — ' + name) if name else ''}")
        else:
            await self._reply(event, f"Multica 连接失败: {result['message']}")

    async def _cmd_sync(self, event: MessageEvent) -> None:
        from .multica_client import MulticaClient

        client = MulticaClient(self.cfg)
        result = await client.sync_data({"source": "command"})
        if result["ok"]:
            await self._reply(event, "数据同步已触发")
        else:
            await self._reply(event, f"同步失败: {result['message']}")

    @staticmethod
    async def _reply(event: MessageEvent, text: str) -> None:
        """向消息来源回复。"""
        try:
            # AstrBot 标准回复方式
            if hasattr(event, "reply"):
                await event.reply(text)
            elif hasattr(event, "send"):
                await event.send(text)
        except Exception as e:
            logger.warning("[multica_bridge] 回复消息失败: %s", e)
