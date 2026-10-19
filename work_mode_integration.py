"""AstrBot lifecycle and command permissions for the standalone work service."""

from __future__ import annotations

from .astrbot_compat import WorkModeRouter
from .reply_worker import PREFIX
from .session_store import SessionStore
from .work_mode import COMMAND, WorkMode


class WorkModeMixin:
    async def initialize_work_mode(self) -> None:
        self._work_mode = None
        self._work_router = None
        self._work_error = ""
        try:

            async def push(origin, text):
                from astrbot.api.event import MessageChain
                from astrbot.core.message.components import Plain

                result = await self.context.send_message(
                    origin, MessageChain([Plain(text)])
                )
                if result is False:
                    raise RuntimeError("Platform delivery was rejected")

            self._work_mode = WorkMode(
                self, SessionStore(self._data_dir), self._reply, push
            )
            from astrbot.core.star.session_plugin_manager import SessionPluginManager

            async def session_enabled(event):
                return await SessionPluginManager.is_plugin_enabled_for_session(
                    event.unified_msg_origin, self.name
                )

            router = WorkModeRouter(
                self._work_mode,
                permission=self.authorize_work_event,
                session_enabled=session_enabled,
            )
            router.install()
            self._work_router = router
            self._work_mode.resume()
        except Exception as exc:
            self._work_error = type(exc).__name__
            self.log.warning(
                "[multica_bridge] Work-mode initialization unavailable (%s)",
                self._work_error,
            )

    async def terminate(self) -> None:
        router = getattr(self, "_work_router", None)
        if router:
            router.uninstall()
        service = getattr(self, "_work_mode", None)
        if service:
            await service.close()

    def _find_work_handler(self, event, override: str = ""):
        from astrbot.core.star.filter.command import CommandFilter
        from astrbot.core.star.star_handler import EventType, star_handlers_registry

        text = (event.message_str or "").strip()
        match = COMMAND.fullmatch(text)
        command = override or "multica " + (
            (match.group(1) or "enter").strip() if match else "enter"
        )
        best, length = None, -1
        # Inspect disabled commands too; the public query intentionally omits
        # them and treating a missing disabled handler as unknown would bypass it.
        for handler in star_handlers_registry:
            if (
                handler.event_type != EventType.AdapterMessageEvent
                or handler.handler_module_path != type(self).__module__
            ):
                continue
            for item in handler.event_filters:
                if not isinstance(item, CommandFilter):
                    continue
                for name in item.get_complete_command_names():
                    if (
                        command.casefold() == name.casefold()
                        or command.casefold().startswith(name.casefold() + " ")
                    ):
                        if len(name) > length:
                            best, length = handler, len(name)
        return best

    def authorize_work_event(self, event, cfg: dict) -> bool:
        from astrbot.core.star.filter.command import CommandFilter
        from astrbot.core.star.filter.command_group import CommandGroupFilter

        handler = self._find_work_handler(event)
        if handler is None:
            # Unknown /multica controls only display help; no external operation.
            return (
                True if COMMAND.fullmatch((event.message_str or "").strip()) else False
            )
        checks = [handler]
        match = COMMAND.fullmatch((event.message_str or "").strip())
        action = ((match.group(1) or "enter").split()[0] if match else "enter").lower()
        if action in {"enter", "new", "agent"}:
            entry = self._find_work_handler(event, "multica enter")
            if entry is None:
                return False
            checks.append(entry)
        for candidate in checks:
            if not candidate.enabled:
                return False
            for item in candidate.event_filters:
                if isinstance(item, (CommandFilter, CommandGroupFilter)):
                    if not item.custom_filter_ok(event, cfg):
                        return False
                elif not item.filter(event, cfg):
                    return False
        return True

    async def dispatch_legacy(self, event, tail: str) -> None:
        handler = self._find_work_handler(event)
        if handler is None:
            await self._work_mode.reply(event, "未知命令，请使用 /multica help。")
            return
        await getattr(self, handler.handler_name)(event)

    async def work_control(self, event) -> None:
        # Normally handled before command filtering. This is the fail-closed path
        # if AstrBot no longer exposes the supported pipeline entry.
        if not getattr(self, "_work_router", None):
            await self._reply(
                event,
                PREFIX
                + "当前无法安全接管消息，未进入工作模式。请检查插件日志及 AstrBot 版本。",
            )
            event.stop_event()
            return
        if not event.message_str.startswith("/"):
            event.message_str = "/" + event.message_str
        await self._work_mode.handle(event)
