import asyncio
import importlib
from types import SimpleNamespace

from test_commands import _install_astrbot_stubs
from test_work_mode import Event, setup_service


def test_dashboard_lists_scoped_work_sessions_and_can_exit_one(
    tmp_path, monkeypatch, nl_plugin
):
    async def run():
        web = importlib.import_module("astrbot_plugin_multica_bridge.web_api")
        plugin, register, _ = nl_plugin
        register("enter")
        plugin.cfg = {
            "enabled": True,
            "work_mode_enabled": True,
            "token": "must-stay-private",
            "api_url": "https://example.test",
            "multica_whitelist": ["u1"],
        }
        service, _, _ = setup_service(tmp_path)
        service.plugin = plugin
        plugin._work_mode, plugin._work_router = service, object()
        try:
            await service.handle(Event())
            await service.handle(Event(group="B"))
            status = await plugin.api_work_status()
            assert status["success"]
            assert len(status["data"]["sessions"]) == 2
            assert "must-stay-private" not in str(status)
            key = status["data"]["sessions"][0]["key"]

            async def body():
                return {"key": key}

            monkeypatch.setattr(web, "_read_json_body", body)
            assert (await plugin.api_action_exit_session())["success"]
            remaining = (await plugin.api_work_status())["data"]["sessions"]
            assert len(remaining) == 1
            assert service.should_route(
                Event("still work", group=remaining[0]["chat_id"])
            )
        finally:
            await service.close()

    asyncio.run(run())


def test_context_options_are_returned_without_credentials(tmp_path, monkeypatch):
    async def run():
        _install_astrbot_stubs()
        main = importlib.import_module("astrbot_plugin_multica_bridge.main")
        client = importlib.import_module("astrbot_plugin_multica_bridge.multica_client")
        plugin = main.Main(SimpleNamespace())
        plugin.cfg = {"token": "secret"}

        async def workspaces(self):
            return {
                "ok": True,
                "workspaces": [
                    {"id": "ws1", "name": "A", "slug": "a", "private_field": "secret"}
                ],
            }

        monkeypatch.setattr(client.MulticaClient, "list_workspaces", workspaces)
        result = await plugin.api_action_list_workspaces()
        assert result["data"]["workspaces"] == [{"id": "ws1", "name": "A", "slug": "a"}]
        assert "secret" not in str(result)

    asyncio.run(run())
