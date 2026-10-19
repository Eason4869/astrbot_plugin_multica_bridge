import asyncio

import pytest
from astrbot_plugin_multica_bridge.multica_client import MulticaClient
from astrbot_plugin_multica_bridge.nl_control import parse_nl_intent
from test_work_mode import Event, setup_service


def test_business_keyword_is_preserved():
    intent = parse_nl_intent("建个issue：multica 登录失败")
    assert "multica" in intent.args


def test_stop_during_first_creation_discards_queued_text(tmp_path):
    async def run():
        service, client, _ = setup_service(tmp_path)
        started, proceed = asyncio.Event(), asyncio.Event()
        original = client.create_chat

        async def slow(*args):
            started.set()
            await proceed.wait()
            return await original(*args)

        client.create_chat = slow
        entering = asyncio.create_task(service.handle(Event()))
        tasks = [entering]
        try:
            await started.wait()
            tasks.append(asyncio.create_task(service.handle(Event("old task"))))
            await asyncio.sleep(0)
            await service.handle(Event("/multica stop"))
            proceed.set()
            await asyncio.gather(*tasks)
            assert not client.sent
        finally:
            proceed.set()
            await asyncio.gather(*tasks, return_exceptions=True)
            await service.close()

    asyncio.run(run())


@pytest.mark.parametrize("stage", ["agents", "history"])
@pytest.mark.parametrize("revocation", ["disabled", "admin", "custom"])
def test_revoking_command_during_await_prevents_write(
    nl_plugin, tmp_path, stage, revocation
):
    plugin, register, _ = nl_plugin
    handler = register("enter")
    plugin.cfg.update(multica_whitelist=["u1"], work_mode_enabled=True)

    def revoke():
        from test_authorization import AdminOnly

        if revocation == "disabled":
            handler.enabled = False
        elif revocation == "admin":
            handler.event_filters.append(AdminOnly())
        else:
            handler.event_filters[0].custom_filter_ok = lambda event, cfg: False

    async def run():
        service, client, _ = setup_service(tmp_path)
        service.plugin = plugin
        try:
            if stage == "history":
                await service.handle(Event())
                await service.worker.close()

                async def changed(*args):
                    revoke()
                    return []

                client.messages = changed
                event = Event("do not send")
                event.role = "member"
                await service.handle(event)
                assert not client.sent
            else:
                original = client.list_agents

                async def changed():
                    revoke()
                    return await original()

                client.list_agents = changed
                event = Event()
                event.role = "member"
                await service.handle(event)
                assert not client.created
        finally:
            await service.close()

    asyncio.run(run())


@pytest.mark.parametrize("kind", ["workspace", "project"])
def test_legacy_selection_does_not_commit_stale_context(nl_plugin, monkeypatch, kind):
    plugin, _, replies = nl_plugin
    plugin.cfg.update(workspace_id="ws-A", project_id="old")
    plugin._save_cfg = lambda: pytest.fail("must not save stale response")

    async def changed(self):
        plugin.cfg = dict(plugin.cfg, workspace_id="ws-B", project_id="")
        return {
            "ok": True,
            "projects": [{"id": "p-A", "workspace_id": "ws-A"}],
            "workspaces": [{"id": "ws-A", "slug": "demo"}],
        }

    monkeypatch.setattr(MulticaClient, "list_" + kind + "s", changed)
    method = getattr(plugin, "_cmd_" + kind + "_select")
    asyncio.run(method(Event(), "p-A" if kind == "project" else "ws-A"))
    assert plugin.cfg["workspace_id"] == "ws-B"
    assert plugin.cfg["project_id"] == ""
    assert replies and "变化" in replies[-1]


@pytest.mark.parametrize("kind", ["chat", "issue"])
def test_stale_project_rejected_before_external_write(monkeypatch, kind):
    from astrbot_plugin_multica_bridge.chat_client import ChatClient, MulticaError

    async def projects(self):
        return {"ok": True, "projects": [{"id": "p-B", "workspace_id": "ws-B"}]}

    monkeypatch.setattr(MulticaClient, "list_projects", projects)

    async def run():
        cfg = {
            "enabled": True,
            "api_url": "https://example.test",
            "token": "test",
            "workspace_id": "00000000-0000-0000-0000-000000000001",
            "project_id": "p-B",
        }
        if kind == "issue":
            result = await MulticaClient(cfg).create_issue(title="demo")
            assert not result["ok"] and "项目" in result["message"]
        else:
            client = ChatClient(cfg)

            async def no_write(*args):
                pytest.fail("invalid project must not reach POST")

            client._object = no_write
            with pytest.raises(MulticaError, match="项目"):
                await client.create_chat("agent", "demo", "p-B")

    asyncio.run(run())
