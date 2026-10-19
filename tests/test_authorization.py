import sys
import types
from types import SimpleNamespace

from astrbot_plugin_multica_bridge.work_mode_integration import WorkModeMixin
from test_work_mode import Event


class CommandFilter:
    def __init__(self, name):
        self.name = name

    def get_complete_command_names(self):
        return [self.name]

    def custom_filter_ok(self, event, cfg):
        return True


class AdminOnly:
    def filter(self, event, cfg):
        return event.role == "admin"


class Plugin(WorkModeMixin):
    pass


def test_reimplanted_command_permissions_and_disabled_commands_are_enforced(
    monkeypatch,
):
    commands = types.ModuleType("astrbot.core.star.filter.command")
    commands.CommandFilter = CommandFilter
    groups = types.ModuleType("astrbot.core.star.filter.command_group")
    groups.CommandGroupFilter = type("CommandGroupFilter", (), {})
    registry = types.ModuleType("astrbot.core.star.star_handler")
    registry.EventType = SimpleNamespace(AdapterMessageEvent="message")

    def handler(name, enabled=True, admin=False):
        return SimpleNamespace(
            event_type="message",
            handler_module_path=Plugin.__module__,
            handler_name="multica_" + name,
            enabled=enabled,
            event_filters=[CommandFilter("multica " + name)]
            + ([AdminOnly()] if admin else []),
        )

    entry = handler("enter", admin=True)
    registry.star_handlers_registry = [
        entry,
        handler("new"),
        handler("agent"),
        handler("exit"),
    ]
    for name, module in [
        (commands.__name__, commands),
        (groups.__name__, groups),
        (registry.__name__, registry),
    ]:
        monkeypatch.setitem(sys.modules, name, module)
    plugin = Plugin()
    for command in [
        "/multica",
        "/multica new",
        "/multica NEW",
        "/multica agent 1",
        "ordinary work",
    ]:
        event = Event(command)
        event.role = "member"
        assert not plugin.authorize_work_event(event, {})
        event.role = "admin"
        assert plugin.authorize_work_event(event, {})
    entry.enabled = False
    event = Event()
    event.role = "admin"
    assert not plugin.authorize_work_event(event, {})
    event = Event("/multica exit")
    event.role = "member"
    assert plugin.authorize_work_event(event, {})
