import importlib

import pytest


class Event:
    def __init__(self, group="A", user="u1", platform="qq-1", self_id="bot"):
        self.group, self.user, self.platform, self.self_id = (
            group,
            user,
            platform,
            self_id,
        )

    def get_group_id(self):
        return self.group

    def get_sender_id(self):
        return self.user

    def get_platform_id(self):
        return self.platform

    def get_self_id(self):
        return self.self_id


def test_group_is_shared_but_other_windows_are_independent(tmp_path):
    module = importlib.import_module("astrbot_plugin_multica_bridge.session_store")
    store = module.SessionStore(str(tmp_path))
    group_a = module.conversation_key(Event())
    assert group_a == module.conversation_key(Event(user="u2"))
    keys = [
        group_a,
        module.conversation_key(Event(group="B")),
        module.conversation_key(Event(group="", user="C")),
        module.conversation_key(Event(platform="qq-2")),
        module.conversation_key(Event(self_id="bot2")),
    ]
    assert len(set(keys)) == 5
    store.update(group_a, active=True, session_id="chat-a", origin="qq:GroupMessage:A")
    restored = module.SessionStore(str(tmp_path))
    assert restored.get(group_a)["active"]
    assert all(not restored.get(key)["active"] for key in keys[1:])
    assert not (tmp_path / "config.json").exists()


def test_old_generation_cannot_commit_after_exit_or_new_chat(tmp_path):
    module = importlib.import_module("astrbot_plugin_multica_bridge.session_store")
    store = module.SessionStore(str(tmp_path))
    current = store.update("room", active=True, session_id="chat-a")
    store.update("room", active=False, generation=current["generation"] + 1)
    assert not store.commit_delivery("room", current["generation"], "reply-old", 0)
    assert store.get("room")["cursor"] == ""


def test_bad_state_file_refuses_silent_loss(tmp_path):
    module = importlib.import_module("astrbot_plugin_multica_bridge.session_store")
    (tmp_path / "work-mode.json").write_text("broken", encoding="utf-8")
    with pytest.raises(ValueError):
        module.SessionStore(str(tmp_path))
