import asyncio
import importlib
import json
from types import SimpleNamespace

from test_commands import _install_astrbot_stubs
from test_upgrade import OLD


def test_main_initialize_and_settings_roundtrip_keep_legacy_data_path_and_credentials(
    tmp_path, monkeypatch
):
    async def run():
        _install_astrbot_stubs()
        main = importlib.import_module("astrbot_plugin_multica_bridge.main")
        web = importlib.import_module("astrbot_plugin_multica_bridge.web_api")
        directory = tmp_path / "plugin_data" / "astrbot_plugin_multica_bridge"
        directory.mkdir(parents=True)
        file = directory / "config.json"
        file.write_text(json.dumps(OLD), encoding="utf-8")
        original = file.read_bytes()
        monkeypatch.setattr(main, "get_astrbot_data_path", lambda: str(tmp_path))
        plugin = main.Main(SimpleNamespace(register_web_api=lambda *args: None))
        plugin.name = "astrbot_plugin_multica_bridge"
        await plugin.initialize()
        assert plugin.cfg["token"] == OLD["token"]
        assert plugin.cfg["api_url"] == OLD["api_url"]
        assert file.read_bytes() == original

        async def body():
            return {"default_agent_id": "agent-new", "token": "", "api_url": ""}

        monkeypatch.setattr(web, "_read_json_body", body)
        result = await plugin.api_action_save_config()
        assert result["success"]
        await plugin.terminate()
        reloaded = main.Main(SimpleNamespace(register_web_api=lambda *args: None))
        reloaded.name = "astrbot_plugin_multica_bridge"
        await reloaded.initialize()
        assert reloaded.cfg["token"] == OLD["token"]
        assert reloaded.cfg["api_url"] == OLD["api_url"]
        assert reloaded.cfg["default_agent_id"] == "agent-new"
        assert "old-working-secret" not in str(await reloaded.api_config())
        await reloaded.terminate()

    asyncio.run(run())
