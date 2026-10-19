"""Small, reversible compatibility boundary around AstrBot's pipeline entry.

Only selected window events use the bridge route. Global registries, the core
source files and other windows are never modified. Real access/safety stages
run before the bridge; command filters, session waiters and LLM stages do not.
"""

from __future__ import annotations

import inspect

GUARDS = (
    "WhitelistCheckStage",
    "SessionStatusCheckStage",
    "RateLimitStage",
    "ContentSafetyCheckStage",
)


class WorkModeRouter:
    def __init__(
        self, service, scheduler_class=None, permission=None, session_enabled=None
    ):
        if scheduler_class is None:
            from astrbot.core.pipeline.scheduler import PipelineScheduler

            scheduler_class = PipelineScheduler
        self.service, self.scheduler_class = service, scheduler_class
        self.permission = permission
        self.session_enabled = session_enabled
        self.original = None
        self.wrapper = None

    def install(self) -> None:
        cls = self.scheduler_class
        old = getattr(cls, "_multica_bridge_router", None)
        if old:
            old.uninstall()
        original = cls._process_stages
        if list(inspect.signature(original).parameters) != [
            "self",
            "event",
            "from_stage",
        ]:
            raise RuntimeError("Unsupported AstrBot pipeline entry signature")
        self.original = original
        router = self

        async def route(scheduler, event, from_stage=0):
            event._multica_scheduler = scheduler
            if (
                from_stage
                or router.service.closed
                or not router.service.should_route(event)
            ):
                return await original(scheduler, event, from_stage)
            try:
                event._multica_owned = True
                await router._owned(scheduler, event)
            except Exception:
                # An owned event never falls back to normal plugin/LLM processing.
                await router.service.reply(
                    event,
                    "工作模式处理异常，消息未交给普通模型；/multica exit 可退出。",
                )
            finally:
                event.stop_event()

        self.wrapper = route
        cls._process_stages = route
        cls._multica_bridge_router = self

    async def _owned(self, scheduler, event) -> None:
        cfg = scheduler.ctx.astrbot_config
        # Work mode receives every message in the window. Never feed the bot's
        # own echoed output back to Multica, regardless of the ordinary wake policy.
        if event.get_self_id() and str(event.get_self_id()) == str(
            event.get_sender_id()
        ):
            return
        # WakingCheck normally sets role; preserve its authoritative admin rules.
        event.role = "member"
        extra = getattr(event, "get_extra", lambda *a, **kw: None)
        if extra("_api_key_allow_admin_role") is not False and str(
            event.get_sender_id()
        ) in [str(v) for v in cfg.get("admins_id", [])]:
            event.role = "admin"
        event.is_wake = True
        event.is_at_or_wake_command = True
        enabled = cfg.get("plugin_set", ["*"])
        if enabled != ["*"] and "astrbot_plugin_multica_bridge" not in enabled:
            return
        if self.session_enabled and not await self.session_enabled(event):
            return
        available = {type(stage).__name__: stage for stage in scheduler.stages}
        if not all(name in available for name in GUARDS):
            await self.service.reply(
                event, "当前 AstrBot 管线不兼容，未进入工作模式；请更新 AstrBot。"
            )
            return
        for name in GUARDS:
            result = available[name].process(event)
            if inspect.isasyncgen(result):
                try:
                    async for _ in result:
                        # Safety-stage rejection results are not passed through
                        # response decorators, which could invoke other plugins.
                        if event.get_result():
                            await self.service.reply(
                                event, "消息被 AstrBot 内容安全规则拦截。"
                            )
                        return
                finally:
                    await result.aclose()
            else:
                await result
            if event.is_stopped():
                return
        allowed = getattr(self.service.plugin, "_chat_allowed", None)
        if allowed and not allowed(event):
            from .multica_client import PERMISSION_DENIED

            # Denial is deliberately exact, without the work-result prefix.
            await self.service.say(event, PERMISSION_DENIED)
            return
        if self.permission and not self.permission(event, cfg):
            await self.service.reply(event, "权限不足，无法执行此 Multica 操作。")
            return
        await self.service.handle(event)

    def uninstall(self) -> None:
        if self.wrapper and self.scheduler_class._process_stages is self.wrapper:
            self.scheduler_class._process_stages = self.original
        if getattr(self.scheduler_class, "_multica_bridge_router", None) is self:
            delattr(self.scheduler_class, "_multica_bridge_router")
        self.wrapper = None
