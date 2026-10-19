"""Run unmodified upstream classes without starting databases/platform adapters.

AST loading removes only module imports and unrelated declarations. The executed
scheduler, group filter and whitelist class bodies come verbatim from checkouts.
This is source integration, not a real QQ or full AstrBot deployment test.
"""

import ast
import asyncio
import logging
import os
import re
from collections.abc import AsyncGenerator
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from astrbot_plugin_multica_bridge.astrbot_compat import GUARDS, WorkModeRouter
from test_routing import Guard
from test_work_mode import Event, setup_service

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [ROOT / ".validation" / "AstrBot-4.27.2", ROOT / ".validation" / "AstrBot"]


def upstream_class(path, name, namespace):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)
    module = ast.Module(
        body=[
            ast.ImportFrom(
                module="__future__", names=[ast.alias(name="annotations")], level=0
            ),
            node,
        ],
        type_ignores=[],
    )
    ast.fix_missing_locations(module)
    exec(compile(module, str(path), "exec"), namespace)
    return namespace[name]


@pytest.mark.parametrize("source", SOURCES, ids=["AstrBot-4.27.2", "AstrBot-4.29.1"])
def test_upstream_scheduler_command_filter_and_whitelist(source, tmp_path):
    if not source.exists():
        if os.getenv("REQUIRE_UPSTREAM_TESTS"):
            pytest.fail("Required AstrBot checkout missing")
        pytest.skip("Checkout upstream AstrBot to run source integration")

    async def run():
        namespace = {
            "logger": logging.getLogger("upstream"),
            "AsyncGenerator": AsyncGenerator,
            "cast": cast,
            "Stage": object,
            "HandlerFilter": object,
            "re": re,
            "CustomFilter": type("CustomFilter", (), {}),
            "register_stage": lambda cls: cls,
        }
        base = source / "astrbot/core"
        scheduler_class = upstream_class(
            base / "pipeline/scheduler.py", "PipelineScheduler", namespace
        )
        namespace["CommandFilter"] = type("CommandFilter", (), {})
        group_class = upstream_class(
            base / "star/filter/command_group.py", "CommandGroupFilter", namespace
        )
        whitelist_class = upstream_class(
            base / "pipeline/whitelist_check/stage.py", "WhitelistCheckStage", namespace
        )
        command_filter = group_class("other")
        ordinary = []

        class WakingCheckStage:
            async def process(self, event):
                event.is_at_or_wake_command = True
                event.message_str = event.message_str.lstrip("/")
                try:
                    command_filter.filter(event, {})
                except ValueError:
                    ordinary.append("other-plugin-parameter-reply")
                    event.stop_event()

        class ProcessStage:
            async def process(self, event):
                ordinary.extend(["session-waiter", "other-plugin", "default-model"])

        whitelist = whitelist_class()
        whitelist.enable_whitelist_check = False
        whitelist.whitelist = ["allowed-only"]
        whitelist.wl_ignore_admin_on_group = False
        whitelist.wl_ignore_admin_on_friend = False
        whitelist.wl_log = False
        scheduler = object.__new__(scheduler_class)
        scheduler.ctx = SimpleNamespace(
            astrbot_config={
                "admins_id": [],
                "platform_settings": {},
                "plugin_set": ["*"],
            }
        )
        scheduler.stages = [
            WakingCheckStage(),
            whitelist,
            *[Guard(n) for n in GUARDS[1:]],
            ProcessStage(),
        ]
        # Negative control: the real group filter replies before any listener.
        await scheduler._process_stages(Event("/other", group="B"))
        assert ordinary == ["other-plugin-parameter-reply"]
        ordinary.clear()
        service, client, _ = setup_service(tmp_path)
        router = WorkModeRouter(service, scheduler_class, permission=lambda e, c: True)
        original = scheduler_class._process_stages
        router.install()
        try:
            await scheduler._process_stages(Event())
            assert len(client.created) == 1
            for text in ["/other", "/other missing", "普通文字", ""]:
                await scheduler._process_stages(Event(text))
            assert ordinary == []
            whitelist.enable_whitelist_check = True
            count = len(client.sent)
            await scheduler._process_stages(Event("blocked"))
            assert len(client.sent) == count
            whitelist.enable_whitelist_check = False
            await scheduler._process_stages(Event("ordinary", group="B"))
            assert ordinary == ["session-waiter", "other-plugin", "default-model"]
            ordinary.clear()
            await scheduler._process_stages(Event("/multica exit"))
            await scheduler._process_stages(Event("ordinary"))
            assert "default-model" in ordinary
        finally:
            router.uninstall()
            await service.close()
        assert scheduler_class._process_stages is original

    asyncio.run(run())
