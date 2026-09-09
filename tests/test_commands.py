"""指令注册结构与参数解析测试。

CI 中不安装 AstrBot，因此这里用最小 stub 替换 AstrBot 运行时。
stub 严格复刻 AstrBot 的装饰器语义（见官方文档
``docs/zh/dev/star/plugin.md`` 的「指令组」章节）：

- ``@filter.command_group(name)`` 返回 ``RegisteringCommandable``；
- ``RegisteringCommandable.command`` / ``.group`` 是**未绑定函数**，
  所以 ``group.command("x")`` 实际是 ``register_command(group, "x")``（子指令），
  这正是 ``@math.command("add")`` 会注册成 ``math add`` 的原因。

因此本测试能真实覆盖：装饰器用法、指令树层级、别名与完整指令名。
"""

from __future__ import annotations

import importlib
import logging
import sys
import types

import pytest

REGISTERED: list[str] = []


class _Group:
    """复刻 CommandGroupFilter 的完整指令名推导。"""

    def __init__(self, name, parent=None, alias=None):
        self.name = name
        self.parent = parent
        self.alias = set(alias or ())

    def complete_names(self) -> list[str]:
        if self.parent is None:
            return [self.name, *sorted(self.alias)]
        out = []
        for parent_name in self.parent.complete_names():
            for candidate in [self.name, *sorted(self.alias)]:
                out.append(f"{parent_name} {candidate}")
        return out


class RegisteringCommandable:
    def __init__(self, parent_group: _Group):
        self.parent_group = parent_group


def _register_command(command_name=None, sub_command=None, alias=None, **_kwargs):
    if isinstance(command_name, RegisteringCommandable):
        if sub_command is None:
            raise AssertionError("注册子指令必须提供 sub_command")
        for parent_name in command_name.parent_group.complete_names():
            for candidate in [sub_command, *sorted(alias or ())]:
                REGISTERED.append(f"{parent_name} {candidate}")
    else:
        REGISTERED.append(str(command_name))

    def decorator(fn):
        return fn

    return decorator


def _register_command_group(command_group_name=None, sub_command=None, alias=None, **_kwargs):
    if isinstance(command_group_name, RegisteringCommandable):
        group = _Group(sub_command, parent=command_group_name.parent_group, alias=alias)
    else:
        group = _Group(command_group_name, alias=alias)

    def decorator(_fn):
        return RegisteringCommandable(group)

    return decorator


RegisteringCommandable.command = _register_command
RegisteringCommandable.group = _register_command_group


def _install_astrbot_stubs() -> None:
    """把 astrbot 相关模块替换为最小 stub。"""
    astrbot = types.ModuleType("astrbot")
    astrbot.logger = logging.getLogger("astrbot_stub")

    class AstrMessageEvent:  # noqa: N801
        message_str = ""

    class MessageChain:
        def __init__(self, chain=None):
            self.chain = chain or []

    class Plain:
        def __init__(self, text=""):
            self.text = text

    class Context:
        pass

    class Star:
        def __init__(self, context, config=None):
            self.context = context
            self.logger = logging.getLogger("astrbot_stub.plugin")

    filter_mod = types.ModuleType("astrbot.api.event.filter")
    event_mod = types.ModuleType("astrbot.api.event")
    event_mod.AstrMessageEvent = AstrMessageEvent
    event_mod.MessageChain = MessageChain
    event_mod.filter = types.SimpleNamespace(
        command=_register_command,
        command_group=_register_command_group,
    )
    star_mod = types.ModuleType("astrbot.api.star")
    star_mod.Context = Context
    star_mod.Star = Star
    components_mod = types.ModuleType("astrbot.core.message.components")
    components_mod.Plain = Plain
    path_mod = types.ModuleType("astrbot.core.utils.astrbot_path")
    path_mod.get_astrbot_data_path = lambda: "/tmp/astrbot"

    modules = {
        "astrbot": astrbot,
        "astrbot.api": types.ModuleType("astrbot.api"),
        "astrbot.api.event": event_mod,
        "astrbot.api.event.filter": filter_mod,
        "astrbot.api.star": star_mod,
        "astrbot.core": types.ModuleType("astrbot.core"),
        "astrbot.core.message": types.ModuleType("astrbot.core.message"),
        "astrbot.core.message.components": components_mod,
        "astrbot.core.utils": types.ModuleType("astrbot.core.utils"),
        "astrbot.core.utils.astrbot_path": path_mod,
    }
    sys.modules.update(modules)


@pytest.fixture(scope="module")
def plugin_main():
    _install_astrbot_stubs()
    module = importlib.import_module("astrbot_plugin_multica_bridge.main")
    return module


EXPECTED_COMMANDS = {
    # 一级
    "multica help",
    "multica 帮助",
    "multica h",
    "multica status",
    "multica 状态",
    "multica inbox",
    "multica 收件箱",
    # issue
    "multica issue create",
    "multica issue 新建",
    "multica 议题 create",
    "multica 议题 新建",
    # workspace
    "multica workspace list",
    "multica workspace 列表",
    "multica workspace select",
    "multica workspace 选择",
    "multica workspace 切换",
    "multica workspace create",
    "multica workspace 新建",
    "multica 工作区 list",
    "multica 工作区 列表",
    "multica 工作区 select",
    "multica 工作区 选择",
    "multica 工作区 切换",
    "multica 工作区 create",
    "multica 工作区 新建",
    # project
    "multica project list",
    "multica project 列表",
    "multica project select",
    "multica project 选择",
    "multica project 切换",
    "multica project create",
    "multica project 新建",
    "multica 项目 list",
    "multica 项目 列表",
    "multica 项目 select",
    "multica 项目 选择",
    "multica 项目 切换",
    "multica 项目 create",
    "multica 项目 新建",
}


def test_registers_expected_command_tree(plugin_main) -> None:
    assert set(REGISTERED) == EXPECTED_COMMANDS


def test_every_leaf_is_under_multica(plugin_main) -> None:
    assert REGISTERED, "没有注册任何指令"
    for name in REGISTERED:
        assert name.startswith("multica"), name


def test_handlers_are_unique(plugin_main) -> None:
    """每条子指令都必须有独立 handler，才能在指令管理中单独授权。"""
    names = [
        value
        for key, value in vars(plugin_main.Main).items()
        if key.startswith("multica_") and callable(value)
    ]
    assert len(names) == len(set(names))


class TestParseFlags:
    def test_with_flags(self, plugin_main) -> None:
        head, values = plugin_main.Main._parse_flags(
            "修复登录 --desc 用户反馈 --slug fix-login",
            ("--desc", "--slug"),
        )
        assert head == "修复登录"
        assert values == {"--desc": "用户反馈", "--slug": "fix-login"}

    def test_without_flags(self, plugin_main) -> None:
        head, values = plugin_main.Main._parse_flags("只是一个标题", ("--desc",))
        assert head == "只是一个标题"
        assert values == {}

    def test_empty_value_is_detected(self, plugin_main) -> None:
        _head, values = plugin_main.Main._parse_flags("标题 --desc", ("--desc",))
        assert values == {"--desc": ""}

    def test_flag_before_title(self, plugin_main) -> None:
        head, values = plugin_main.Main._parse_flags("--desc 描述", ("--desc",))
        assert head == ""
        assert values == {"--desc": "描述"}


class TestArgs:
    def test_strips_command_words(self, plugin_main) -> None:
        event = types.SimpleNamespace(message_str="multica workspace create 项目A --slug a")
        assert plugin_main.Main._args(event, 3) == "项目A --slug a"

    def test_no_tail_returns_empty(self, plugin_main) -> None:
        event = types.SimpleNamespace(message_str="multica inbox")
        assert plugin_main.Main._args(event, 2) == ""

    def test_alias_works(self, plugin_main) -> None:
        event = types.SimpleNamespace(message_str="multica 工作区 新建 项目A")
        assert plugin_main.Main._args(event, 3) == "项目A"


class TestFormatIssue:
    def test_basic_line(self, plugin_main) -> None:
        line = plugin_main.Main._format_issue(
            {
                "identifier": "ABC-1",
                "title": "标题",
                "status": "in_progress",
                "priority": "high",
                "assignee_id": "u1",
            },
            {"u1": "小明"},
        )
        assert "ABC-1" in line
        assert "🟡" in line
        assert "[高]" in line
        assert "(小明)" in line

    def test_long_title_is_truncated(self, plugin_main) -> None:
        line = plugin_main.Main._format_issue({"title": "x" * 80})
        assert "…" in line
        assert len(line) < 60
