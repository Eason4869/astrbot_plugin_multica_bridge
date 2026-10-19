import asyncio

from astrbot_plugin_multica_bridge.multica_client import check_chat_allowed
from test_nl_dispatch import nl_plugin  # noqa: F401
from test_work_mode import Event


def test_user_whitelist_is_required_and_has_no_group_or_private_mode():
    assert not check_chat_allowed({}, "user", "42")
    assert not check_chat_allowed({"multica_whitelist": []}, "user", "42")
    assert check_chat_allowed({"multica_whitelist": [42]}, "user", "42")
    assert not check_chat_allowed({"multica_whitelist": ["42"], "group_chat_mode": "disabled"}, "user", "43")


def test_non_whitelisted_command_gets_exact_denial(nl_plugin):
    plugin, _, replies = nl_plugin
    plugin.cfg["multica_whitelist"] = ["allowed"]
    # Use the actual access check, not the permission fixture's stub.
    plugin._chat_allowed = type(plugin)._chat_allowed.__get__(plugin)
    calls = []
    async def business():
        calls.append(True)
    asyncio.run(plugin._run(Event("/multica inbox", user="other"), business))
    assert not calls
    assert replies == ["您没有使用Multica的权限，请联系管理员获取使用资格"]


def test_whitelist_accepts_exact_umo_and_uid_independently():
    cfg = {"multica_whitelist": ["1256138501", "EasonBot:FriendMessage:88"]}
    assert check_chat_allowed(cfg, "user", "1256138501", "Other:GroupMessage:9")
    assert check_chat_allowed(cfg, "user", "88", "EasonBot:FriendMessage:88")
    assert not check_chat_allowed(cfg, "user", "88", "Other:FriendMessage:88")
    assert not check_chat_allowed(cfg, "user", "88", "EasonBot:FriendMessage:888")
