import asyncio

from astrbot_plugin_multica_bridge.multica_client import check_chat_allowed
from test_work_mode import Event


def test_user_whitelist_is_required_and_has_no_group_or_private_mode():
    assert not check_chat_allowed({}, "user", "42")
    assert not check_chat_allowed({"multica_whitelist": []}, "user", "42")
    assert check_chat_allowed({"multica_whitelist": [42]}, "user", "42")
    assert not check_chat_allowed(
        {"multica_whitelist": ["42"], "group_chat_mode": "disabled"}, "user", "43"
    )


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
    cfg = {"multica_whitelist": ["用户QQ号", "机器人ID:FriendMessage:88"]}
    assert check_chat_allowed(cfg, "user", "用户QQ号", "Other:GroupMessage:9")
    assert check_chat_allowed(cfg, "user", "88", "机器人ID:FriendMessage:88")
    assert not check_chat_allowed(cfg, "user", "88", "Other:FriendMessage:88")
    assert not check_chat_allowed(cfg, "user", "88", "机器人ID:FriendMessage:888")


def test_group_umo_grants_members_commands_but_only_starter_is_forwarded(
    nl_plugin, tmp_path
):
    from types import SimpleNamespace

    from astrbot_plugin_multica_bridge.astrbot_compat import GUARDS, WorkModeRouter
    from test_routing import FakeScheduler, Guard
    from test_work_mode import setup_service

    plugin, register, replies = nl_plugin
    register("enter")
    register("exit")
    register("status")
    plugin.cfg["multica_whitelist"] = ["qq:GroupMessage:A"]
    plugin._chat_allowed = type(plugin)._chat_allowed.__get__(plugin)

    async def run():
        service, client, _ = setup_service(tmp_path)
        service.plugin = plugin
        scheduler = FakeScheduler()
        scheduler.ctx = SimpleNamespace(astrbot_config={})
        scheduler.stages = [Guard(name) for name in GUARDS]
        router = WorkModeRouter(
            service, FakeScheduler, permission=plugin.authorize_work_event
        )
        router.install()
        try:
            await scheduler._process_stages(Event(user="any-member"))
            assert len(client.created) == 1
            other = Event("ordinary", user="friend")
            await scheduler._process_stages(other)
            assert not other.stopped and not client.sent
            owner = Event("work", user="any-member")
            owner.unified_msg_origin = "qq:GroupMessage:A_any-member"
            await scheduler._process_stages(owner)
            assert len(client.sent) == 1
            denied = Event("/multica", group="B", user="friend")
            await scheduler._process_stages(denied)
            assert denied.replies == [
                "您没有使用Multica的权限，请联系管理员获取使用资格"
            ]
        finally:
            router.uninstall()
            await service.close()

    asyncio.run(run())
