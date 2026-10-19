"""Local-only browser harness backed by the real plugin configuration API."""

import asyncio
import importlib
import json
import sys
from contextvars import ContextVar
from pathlib import Path
from types import SimpleNamespace

from aiohttp import web

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
importlib.import_module("conftest")
importlib.import_module("test_commands")._install_astrbot_stubs()
connection_key = importlib.import_module(
    "astrbot_plugin_multica_bridge.session_store"
).connection_key

main = importlib.import_module("astrbot_plugin_multica_bridge.main")
web_api = importlib.import_module("astrbot_plugin_multica_bridge.web_api")
body_var = ContextVar("body")


async def read_body():
    return body_var.get()


web_api._read_json_body = read_body


async def start():
    root = ROOT / ".validation/ui-data"
    directory = root / "plugin_data/astrbot_plugin_multica_bridge"
    directory.mkdir(parents=True, exist_ok=True)
    original = {
        "enabled": True,
        "api_url": "http://127.0.0.1:18764/multica",
        "token": "ui-fixture-old-secret",
        "workspace_id": "00000000-0000-0000-0000-000000000001",
        "project_id": "",
        "group_chat_mode": "blacklist",
        "group_chat_list": [],
        "private_chat_mode": "blacklist",
        "private_chat_list": [],
        "nl_enabled": True,
        "nl_llm_enabled": True,
        "nl_keyword": "multica",
    }
    (directory / "config.json").write_text(json.dumps(original), encoding="utf-8")
    main.get_astrbot_data_path = lambda: str(root)

    async def send(*args):
        return True

    plugin = main.Main(
        SimpleNamespace(register_web_api=lambda *args: None, send_message=send)
    )
    plugin.name = "astrbot_plugin_multica_bridge"
    await plugin.initialize()
    plugin._work_router = object()
    plugin._work_mode.store.records = {}
    for key, kind, chat, agent in [
        ("fixture-group", "group", "123456789", "项目开发助手"),
        ("fixture-private", "private", "246801357", "资料整理助手"),
    ]:
        plugin._work_mode.store.update(
            key,
            active=True,
            origin="qq:GroupMessage:" + chat,
            chat_type=kind,
            chat_id=chat,
            agent_name=agent,
            session_id="fixture-chat",
            workspace_id=original["workspace_id"],
            connection=connection_key(plugin.cfg),
        )
    app = web.Application()

    async def page(request):
        locale = request.query.get("locale", "zh-CN")
        translations = json.loads(
            (ROOT / ".astrbot-plugin/i18n" / f"{locale}.json").read_text(
                encoding="utf-8"
            )
        )
        bridge = """<script>window.AstrBotPluginPage={ready:async()=>{},getContext:()=>({isDark:location.search.includes('dark=1')}),onContext:cb=>{window.testTheme=cb},t:(key,fallback)=>key.split('.').reduce((o,k)=>o&&o[k],TRANSLATIONS)||fallback,apiGet:async(path)=>await(await fetch('/plugin/'+path)).json(),apiPost:async(path,body)=>await(await fetch('/plugin/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})})).json()};</script>""".replace(
            "TRANSLATIONS", json.dumps(translations, ensure_ascii=False)
        )
        html = (
            (ROOT / "pages/settings/index.html")
            .read_text(encoding="utf-8")
            .replace("<head>", "<head>" + bridge)
        )
        return web.Response(text=html, content_type="text/html")

    async def api(request):
        action = request.match_info["action"]
        methods = {
            "config": plugin.api_config,
            "work_status": plugin.api_work_status,
            "actions/save_config": plugin.api_action_save_config,
            "actions/test_connection": plugin.api_action_test_connection,
            "actions/list_agents": plugin.api_action_list_agents,
            "actions/exit_session": plugin.api_action_exit_session,
        }
        if action not in methods:
            raise web.HTTPNotFound()
        token = body_var.set(await request.json() if request.method == "POST" else {})
        try:
            return web.json_response(await methods[action]())
        finally:
            body_var.reset(token)

    async def multica(request):
        tail = request.match_info["tail"]
        if tail == "workspaces":
            return web.json_response(
                [
                    {
                        "id": original["workspace_id"],
                        "name": "本地验证工作区",
                        "slug": "validation",
                    }
                ]
            )
        if tail == "agents":
            return web.json_response(
                [
                    {"id": "agent-one", "name": "项目开发助手"},
                    {"id": "agent-two", "name": "资料整理助手"},
                ]
            )
        if tail.endswith("/messages/page"):
            return web.json_response({"messages": [], "has_more": False})
        if tail.endswith("/pending-task"):
            return web.json_response({})
        return web.json_response([])

    app.router.add_get("/", page)
    app.router.add_route("*", "/plugin/{action:.*}", api)
    app.router.add_route("*", "/multica/api/{tail:.*}", multica)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 18764).start()
    print("UI harness ready at http://127.0.0.1:18764", flush=True)
    await asyncio.Event().wait()


asyncio.run(start())
