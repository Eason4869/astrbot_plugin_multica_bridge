import asyncio
import importlib
import types
from types import SimpleNamespace

import pytest
from test_authorization import AdminOnly, CommandFilter
from test_commands import _install_astrbot_stubs
from test_work_mode import Event


@pytest.fixture
def nl_plugin(monkeypatch):
    _install_astrbot_stubs()
    module = importlib.import_module("astrbot_plugin_multica_bridge.main")
    plugin = module.Main(SimpleNamespace(get_config=lambda *a: {}))
    plugin.cfg = {"enabled": True, "nl_enabled": True, "nl_llm_enabled": True}
    plugin._chat_allowed = lambda e: True
    commands = types.ModuleType("astrbot.core.star.filter.command")
    commands.CommandFilter = CommandFilter
    groups = types.ModuleType("astrbot.core.star.filter.command_group")
    groups.CommandGroupFilter = type("CommandGroupFilter", (), {})
    registry = types.ModuleType("astrbot.core.star.star_handler")
    registry.EventType = SimpleNamespace(AdapterMessageEvent="message")
    registry.star_handlers_registry = []
    for mod in (commands, groups, registry):
        monkeypatch.setitem(__import__("sys").modules, mod.__name__, mod)
    replies = []

    async def reply(event, text):
        replies.append(text)

    plugin._reply = reply

    def register(command, admin=False, enabled=True):
        handler = SimpleNamespace(
            event_type="message", handler_module_path=type(plugin).__module__,
            handler_name="unused", enabled=enabled,
            event_filters=[CommandFilter("multica " + command)]
            + ([AdminOnly()] if admin else []),
        )
        registry.star_handlers_registry.append(handler)
        return handler

    return plugin, register, replies


@pytest.mark.parametrize("action,command", [("issue_create", "issue create"), ("inbox", "inbox"), ("project_select", "project select")])
@pytest.mark.parametrize("source", ["rule", "llm"])
def test_natural_actions_cannot_bypass_admin_permission(nl_plugin, action, command, source):
    from astrbot_plugin_multica_bridge.nl_control import NLIntent
    plugin, register, replies = nl_plugin
    register(command, admin=True)
    calls = []

    async def business(*args):
        calls.append(args)

    setattr(plugin, "_cmd_" + action, business)
    event = Event("multica control")
    event.role = "member"
    asyncio.run(plugin._execute_nl_intent(event, NLIntent(action, "target", source)))
    assert not calls
    assert replies


def test_disabled_inbox_cannot_be_called_through_natural_language(nl_plugin):
    from astrbot_plugin_multica_bridge.nl_control import NLIntent
    plugin, register, _ = nl_plugin
    register("inbox", enabled=False)
    event = Event("multica 收件箱")
    event.role = "admin"
    calls = []

    async def inbox(*args):
        calls.append(args)

    plugin._cmd_inbox = inbox
    asyncio.run(plugin._execute_nl_intent(event, NLIntent("inbox")))
    assert not calls


def test_disabled_bridge_does_not_call_provider(nl_plugin):
    plugin, _, _ = nl_plugin
    plugin.cfg["enabled"] = False
    calls = []

    async def parse(*args):
        calls.append(args)
        return None

    plugin._llm_parse_intent = parse
    asyncio.run(plugin.on_multica_natural_language(Event("multica 是什么")))
    assert not calls
