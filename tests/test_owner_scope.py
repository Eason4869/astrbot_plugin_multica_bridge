import asyncio
import json

from astrbot_plugin_multica_bridge.session_store import SessionStore, conversation_key
from test_work_mode import Event, setup_service


def test_only_starter_messages_are_owned_and_other_members_keep_normal_routing(
    tmp_path,
):
    async def run():
        service, client, _ = setup_service(tmp_path)
        try:
            await service.handle(Event(user="owner"))
            assert service.should_route(Event("work", user="owner"))
            other = Event("ordinary", user="friend")
            assert not service.should_route(other)
            await service.handle(other)
            assert not client.sent and not other.stopped
            await service.handle(Event("work", user="owner"))
            assert len(client.sent) == 1
            await service.handle(Event("/multica exit", user="friend"))
            assert service.store.get(conversation_key(Event()))["active"]
        finally:
            await service.close()

    asyncio.run(run())


def test_old_shared_group_without_owner_is_paused_without_overwriting_file(tmp_path):
    path = tmp_path / "work-mode.json"
    raw = json.dumps(
        {
            "version": 1,
            "sessions": {
                "room": {"active": True, "chat_type": "group", "session_id": "old"}
            },
        }
    ).encode()
    path.write_bytes(raw)
    store = SessionStore(str(tmp_path))
    assert not store.get("room")["active"]
    assert path.read_bytes() == raw


def test_old_private_chat_can_safely_infer_owner_without_disk_write(tmp_path):
    path = tmp_path / "work-mode.json"
    raw = json.dumps(
        {
            "version": 1,
            "sessions": {
                "private": {
                    "active": True,
                    "chat_type": "private",
                    "chat_id": "demo-user",
                    "session_id": "chat",
                }
            },
        }
    ).encode()
    path.write_bytes(raw)
    store = SessionStore(str(tmp_path))
    assert store.get("private")["owner_id"] == "demo-user"
    assert store.get("private")["active"]
    assert path.read_bytes() == raw


def test_different_starter_cannot_resume_previous_owners_chat(tmp_path):
    async def run():
        service, client, _ = setup_service(tmp_path)
        try:
            await service.handle(Event(user="owner"))
            await service.handle(Event("/multica exit", user="owner"))
            await service.handle(Event(user="next"))
            assert len(client.created) == 2
        finally:
            await service.close()

    asyncio.run(run())


def test_natural_enter_routes_before_wake_and_preserves_original_text(tmp_path):
    async def run():
        service, client, _ = setup_service(tmp_path)
        try:
            event = Event("切换为multica工作")
            assert service.should_route(event)
            await service.handle(event)
            assert len(client.created) == 1
            assert event.message_str == "切换为multica工作"
            assert service.should_route(Event("work"))
        finally:
            await service.close()

    asyncio.run(run())


def test_non_owner_can_use_independent_commands_but_not_control_starters_chat(tmp_path):
    async def run():
        service, client, _ = setup_service(tmp_path)
        calls = []

        async def dispatch(event, tail):
            calls.append(tail)

        service.plugin.dispatch_legacy = dispatch
        try:
            await service.handle(Event(user="owner"))
            await service.handle(Event("/multica inbox", user="friend"))
            await service.handle(Event("/multica issue create demo", user="friend"))
            status = Event("/multica status", user="friend")
            await service.handle(status)
            assert calls == ["inbox", "issue create demo"]
            assert (
                status.replies
                and "权限" not in status.replies[0]
                and "其他成员" not in status.replies[0]
            )
            await service.handle(Event("/multica new", user="friend"))
            assert len(client.created) == 1
        finally:
            await service.close()

    asyncio.run(run())
