import asyncio
import json

from astrbot_plugin_multica_bridge.session_store import SessionStore, conversation_key
from test_work_mode import Event, setup_service


def test_only_starter_messages_are_owned_and_other_members_keep_normal_routing(tmp_path):
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
    raw = json.dumps({"version": 1, "sessions": {"room": {"active": True, "chat_type": "group", "session_id": "old"}}}).encode()
    path.write_bytes(raw)
    store = SessionStore(str(tmp_path))
    assert not store.get("room")["active"]
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
