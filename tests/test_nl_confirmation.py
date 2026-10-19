import asyncio

from test_work_mode import Event


def test_pending_confirmation_requires_owner_context_expiry_and_single_use():
    from astrbot_plugin_multica_bridge.actions import ActionRequest
    from astrbot_plugin_multica_bridge.pending_intents import PendingIntentStore

    store = PendingIntentStore()
    owner = ("qq", "bot", "room", "u1")
    request = ActionRequest("issue_create", {"title": "fix"})
    code = store.create(owner, request, "ctx", 0)
    assert store.claim(("qq", "bot", "room", "u2"), code, "ctx", 1) is None
    assert store.claim(owner, code, "ctx", 119).fields == {"title": "fix"}
    assert store.claim(owner, code, "ctx", 119) is None
    code = store.create(owner, request, "ctx", 0)
    assert store.claim(owner, code, "ctx", 120) is None
    code = store.create(owner, request, "ctx", 0)
    assert store.claim(owner, code, "different", 1) is None


def test_natural_issue_is_previewed_then_created_once(nl_plugin, monkeypatch):
    from astrbot_plugin_multica_bridge import natural_language as runtime

    plugin, register, replies = nl_plugin
    register("issue create")
    plugin.cfg.update(api_url="https://example.test", token="secret")
    writes = []

    class Client:
        _workspace_id = "ws1"

        def __init__(self, cfg):
            pass

        async def _ensure_workspace_id(self):
            pass

        async def create_issue(self, **fields):
            writes.append(fields)
            return {"ok": True, "message": "created"}

    monkeypatch.setattr(runtime, "MulticaClient", Client)

    async def run():
        await plugin.on_multica_natural_language(
            Event("multica 建个issue：multica 登录失败")
        )
        assert not writes
        import re

        code = re.search(r"确认 (\d{6})", replies[-1])[1]
        await plugin.on_multica_natural_language(Event("确认 " + code, user="other"))
        assert not writes
        await plugin.on_multica_natural_language(Event("确认 " + code))
        await plugin.on_multica_natural_language(Event("确认 " + code))
        assert len(writes) == 1
        assert writes[0]["title"] == "multica 登录失败"

    asyncio.run(run())


def test_revoked_permission_cannot_confirm_old_draft(nl_plugin, monkeypatch):
    from astrbot_plugin_multica_bridge import natural_language as runtime

    plugin, register, replies = nl_plugin
    handler = register("issue create")
    plugin.cfg.update(api_url="https://example.test", token="secret")
    writes = []

    class Client:
        _workspace_id = "ws1"

        def __init__(self, cfg):
            pass

        async def _ensure_workspace_id(self):
            pass

        async def create_issue(self, **fields):
            writes.append(fields)

    monkeypatch.setattr(runtime, "MulticaClient", Client)

    async def run():
        import re

        await plugin.on_multica_natural_language(Event("multica 建个issue：fix"))
        code = re.search(r"确认 (\d{6})", replies[-1])[1]
        handler.enabled = False
        await plugin.on_multica_natural_language(Event("确认 " + code))
        assert not writes

    asyncio.run(run())
