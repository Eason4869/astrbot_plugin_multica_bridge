import asyncio
import importlib
from types import SimpleNamespace

import pytest
from astrbot_plugin_multica_bridge.session_store import SessionStore


class Event:
    def __init__(self, text="/multica", group="A", user="u1", message_id=""):
        self.message_str, self.group, self.user = text, group, user
        self.unified_msg_origin = "qq:GroupMessage:" + (group or user)
        self.message_obj = SimpleNamespace(message_id=message_id)
        self.replies, self.stopped = [], False

    def get_group_id(self):
        return self.group

    def get_sender_id(self):
        return self.user

    def get_sender_name(self):
        return self.user

    def get_platform_id(self):
        return "qq"

    def get_self_id(self):
        return "bot"

    def get_message_type(self):
        return SimpleNamespace(value="GroupMessage" if self.group else "FriendMessage")

    def get_messages(self):
        return []

    def stop_event(self):
        self.stopped = True

    def is_stopped(self):
        return self.stopped

    def get_result(self):
        return None

    def get_extra(self, key, default=None):
        return default


class Client:
    def __init__(self):
        self.sent, self.created, self.history = [], [], []
        self.failure = False
        self._workspace_id = "workspace"

    async def list_agents(self):
        return [{"id": "agent", "name": "开发助手"}]

    async def create_chat(self, agent, title, project=""):
        self.created.append(agent)
        return {"id": f"chat-{len(self.created)}", "status": "active"}

    async def get_chat(self, session):
        return {"id": session, "status": "active"}

    async def messages(self, session, since_id=""):
        return list(self.history)

    async def pending(self, session):
        return {}

    async def send_chat(self, session, content):
        if self.failure:
            raise RuntimeError("PRIVATE TOKEN MUST NOT LEAK")
        self.sent.append((session, content))
        return {"message_id": "m1", "task_id": "t1"}

    async def stop(self, session):
        pass


def setup_service(tmp_path):
    module = importlib.import_module("astrbot_plugin_multica_bridge.work_mode")
    client = Client()
    outputs = []

    async def say(event, text):
        event.replies.append(text)

    async def push(origin, text):
        outputs.append((origin, text))

    plugin = SimpleNamespace(
        cfg={
            "enabled": True,
            "work_mode_enabled": True,
            "api_url": "https://example.test",
            "token": "secret",
        }
    )
    service = module.WorkMode(
        plugin, SessionStore(str(tmp_path)), say, push, lambda cfg: client
    )
    return service, client, outputs


def test_work_mode_group_scope_prefix_continuity_exit_and_reload(tmp_path):
    async def run():
        service, client, _ = setup_service(tmp_path)
        try:
            enter = Event()
            await service.handle(enter)
            assert all(
                text.startswith("【来自 Multica｜工作模式】") for text in enter.replies
            )
            assert service.should_route(Event("hello", user="u2"))
            assert not service.should_route(Event("hello", group="B"))
            assert not service.should_route(Event("hello", group="", user="C"))
            await service.handle(Event("第一问", message_id="q1"))
            await service.handle(Event("第一问", message_id="q1"))
            await service.handle(Event("继续", user="u2", message_id="q2"))
            assert len(client.sent) == 2
            assert all(item[0] == "chat-1" for item in client.sent)
            assert "u2" in client.sent[1][1]
            restored, _, _ = setup_service(tmp_path)
            assert restored.should_route(Event("still working"))
            await restored.close()
            await service.handle(Event("/multica exit"))
            assert not service.should_route(Event("normal"))
            await service.handle(Event())
            assert len(client.created) == 1  # resume, not a new Chat
        finally:
            await service.close()

    asyncio.run(run())


def test_failure_and_nontext_remain_owned_and_hide_raw_error(tmp_path):
    async def run():
        service, client, _ = setup_service(tmp_path)
        try:
            await service.handle(Event())
            client.failure = True
            failed = Event("question")
            await service.handle(failed)
            assert failed.stopped
            assert "PRIVATE" not in "".join(failed.replies)
            assert service.should_route(Event("still owned"))
            unsupported = Event("")
            await service.handle(unsupported)
            assert unsupported.stopped and unsupported.replies
        finally:
            await service.close()

    asyncio.run(run())


def test_new_chat_and_stop_and_status_do_not_call_default_model(tmp_path):
    async def run():
        service, client, _ = setup_service(tmp_path)
        try:
            for text in [
                "/multica",
                "/multica status",
                "/multica stop",
                "/multica new",
            ]:
                event = Event(text)
                await service.handle(event)
                assert event.stopped and event.replies
            assert len(client.created) == 2
        finally:
            await service.close()

    asyncio.run(run())


@pytest.mark.parametrize("command", ["/mulitca", "/multicafoo", "multica是什么"])
def test_no_typo_alias_or_substring_takeover(tmp_path, command):
    service, _, _ = setup_service(tmp_path)
    assert not service.should_route(Event(command))
