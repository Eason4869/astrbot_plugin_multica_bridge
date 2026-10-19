"""HTTP contract tests use a real local aiohttp server, never a fake request."""

import asyncio
import importlib

import pytest
from aiohttp import web


def test_chat_roundtrip_retains_old_url_and_auth_and_uses_workspace():
    async def run():
        calls = []

        async def endpoint(request):
            calls.append(
                (
                    request.method,
                    request.path,
                    dict(request.headers),
                    await request.json() if request.can_read_body else None,
                )
            )
            if request.path.endswith("/agents"):
                return web.json_response([{"id": "agent-1", "name": "开发助手"}])
            if request.path.endswith("/projects"):
                assert (
                    request.query["workspace_id"]
                    == "00000000-0000-0000-0000-000000000001"
                )
                return web.json_response(
                    [
                        {
                            "id": "project-1",
                            "workspace_id": "00000000-0000-0000-0000-000000000001",
                        }
                    ]
                )
            if request.path.endswith("/messages/page"):
                return web.json_response(
                    {
                        "messages": [
                            {"id": "reply-1", "role": "assistant", "content": "你好"}
                        ],
                        "has_more": False,
                    }
                )
            if request.path.endswith("/messages"):
                return web.json_response(
                    {
                        "message_id": "msg-1",
                        "task_id": "task-1",
                        "supports_queue": True,
                    },
                    status=201,
                )
            if request.path.endswith("/sessions"):
                return web.json_response(
                    {"id": "chat-1", "agent_id": "agent-1", "status": "active"},
                    status=201,
                )
            return web.json_response({})

        app = web.Application()
        app.router.add_route("*", "/prefix/api/{tail:.*}", endpoint)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        try:
            module = importlib.import_module(
                "astrbot_plugin_multica_bridge.chat_client"
            )
            client = module.ChatClient(
                {
                    "api_url": f"http://127.0.0.1:{port}/prefix",
                    "token": "old-secret",
                    "workspace_id": "00000000-0000-0000-0000-000000000001",
                }
            )
            assert (await client.list_agents())[0]["id"] == "agent-1"
            assert (await client.create_chat("agent-1", "QQ 工作", "project-1"))[
                "id"
            ] == "chat-1"
            assert (await client.send_chat("chat-1", "你好"))["task_id"] == "task-1"
            assert (await client.messages("chat-1"))[0]["content"] == "你好"
            assert all(
                call[2]["Authorization"] == "Bearer old-secret" for call in calls
            )
            assert all(
                call[2]["X-Workspace-ID"] == "00000000-0000-0000-0000-000000000001"
                for call in calls
                if not call[1].endswith("/projects")
            )
            assert calls[2][3] == {
                "agent_id": "agent-1",
                "title": "QQ 工作",
                "project_id": "project-1",
            }
            assert calls[3][3] == {"content": "你好"}
        finally:
            await runner.cleanup()

    asyncio.run(run())


@pytest.mark.parametrize("status", [401, 403, 404, 500])
def test_api_error_does_not_echo_remote_body_or_token(status):
    async def run():
        async def endpoint(request):
            return web.Response(status=status, text="secret-token-and-private-response")

        app = web.Application()
        app.router.add_route("*", "/{tail:.*}", endpoint)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        try:
            module = importlib.import_module(
                "astrbot_plugin_multica_bridge.chat_client"
            )
            client = module.ChatClient(
                {
                    "api_url": f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}",
                    "token": "secret-token",
                    "workspace_id": "00000000-0000-0000-0000-000000000001",
                }
            )
            with pytest.raises(module.MulticaError) as caught:
                await client.list_agents()
            assert "secret" not in str(caught.value)
            assert caught.value.status == status
        finally:
            await runner.cleanup()

    asyncio.run(run())
