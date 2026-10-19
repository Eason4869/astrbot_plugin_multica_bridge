"""Exercise the router before command filtering, safety stages and model fallback."""

import asyncio
import importlib
from types import SimpleNamespace

from test_work_mode import Event, setup_service


class FakeScheduler:
    async def _process_stages(self, event, from_stage=0):
        for stage in self.stages[from_stage:]:
            await stage.process(event)
            if event.stopped:
                break


class Guard:
    def __init__(self, name, blocked=False):
        self.__class__ = type(name, (Guard,), {})
        self.blocked, self.calls = blocked, 0

    async def process(self, event):
        self.calls += 1
        if self.blocked:
            event.stop_event()


def test_early_takeover_blocks_other_commands_waiter_and_llm_and_restores_on_unload(
    tmp_path,
):
    async def run():
        module = importlib.import_module("astrbot_plugin_multica_bridge.astrbot_compat")
        service, _, _ = setup_service(tmp_path)
        called = []

        class WakingCheckStage:
            async def process(self, event):
                called.append("other-command-filter")

        class ProcessStage:
            async def process(self, event):
                called.extend(["session-waiter", "other-plugin", "default-model"])

        scheduler = FakeScheduler()
        scheduler.ctx = SimpleNamespace(
            astrbot_config={
                "admins_id": [],
                "platform_settings": {},
                "plugin_set": ["*"],
            }
        )
        scheduler.stages = [
            WakingCheckStage(),
            *[Guard(n) for n in module.GUARDS],
            ProcessStage(),
        ]
        original = FakeScheduler._process_stages
        router = module.WorkModeRouter(
            service, FakeScheduler, permission=lambda e, c: True
        )
        router.install()
        try:
            await scheduler._process_stages(Event())
            for text in ["hello", "/other", "/other missing", "/multica status", ""]:
                await scheduler._process_stages(Event(text))
            assert not called
            assert all(
                stage.calls >= 1
                for stage in scheduler.stages
                if isinstance(stage, Guard)
            )
            await scheduler._process_stages(Event("ordinary", group="B"))
            assert called == [
                "other-command-filter",
                "session-waiter",
                "other-plugin",
                "default-model",
            ]
            called.clear()
            await scheduler._process_stages(Event("/multica exit"))
            await scheduler._process_stages(Event("ordinary"))
            assert "default-model" in called
        finally:
            router.uninstall()
            await service.close()
        assert FakeScheduler._process_stages is original

    asyncio.run(run())


def test_access_control_blocks_multica_and_permission_denial_never_falls_through(
    tmp_path,
):
    async def run():
        module = importlib.import_module("astrbot_plugin_multica_bridge.astrbot_compat")
        service, client, _ = setup_service(tmp_path)
        scheduler = FakeScheduler()
        scheduler.ctx = SimpleNamespace(
            astrbot_config={
                "admins_id": [],
                "platform_settings": {},
                "plugin_set": ["*"],
            }
        )
        scheduler.stages = [
            Guard(n, blocked=n == "WhitelistCheckStage") for n in module.GUARDS
        ]
        router = module.WorkModeRouter(
            service, FakeScheduler, permission=lambda e, c: True
        )
        router.install()
        try:
            await scheduler._process_stages(Event())
            assert not client.created
            for stage in scheduler.stages:
                stage.blocked = False
            router.permission = lambda e, c: False
            event = Event()
            await scheduler._process_stages(event)
            assert event.stopped and not client.created
            assert "权限" in "".join(event.replies)
        finally:
            router.uninstall()
            await service.close()

    asyncio.run(run())


def test_bot_echo_is_not_forwarded_even_when_global_self_ignore_is_off(tmp_path):
    async def run():
        module = importlib.import_module("astrbot_plugin_multica_bridge.astrbot_compat")
        service, client, _ = setup_service(tmp_path)
        scheduler = FakeScheduler()
        scheduler.ctx = SimpleNamespace(
            astrbot_config={
                "admins_id": [],
                "platform_settings": {"ignore_bot_self_message": False},
                "plugin_set": ["*"],
            }
        )
        scheduler.stages = [Guard(name) for name in module.GUARDS]
        router = module.WorkModeRouter(
            service, FakeScheduler, permission=lambda e, c: True
        )
        router.install()
        try:
            await scheduler._process_stages(Event())
            await scheduler._process_stages(Event("echoed bot output", user="bot"))
            assert not client.sent
        finally:
            router.uninstall()
            await service.close()

    asyncio.run(run())
