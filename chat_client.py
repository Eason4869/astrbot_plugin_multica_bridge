"""Multica Chat App API. No AstrBot provider is used by this client."""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import quote

import aiohttp

from .multica_client import MulticaClient


class MulticaError(RuntimeError):
    def __init__(self, message: str, status: int = 0, uncertain: bool = False):
        super().__init__(message)
        self.status = status
        self.uncertain = uncertain


class ChatClient(MulticaClient):
    async def _request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        params: dict | None = None,
    ) -> Any:
        if not self.enabled or not self._api_url or not self._token:
            raise MulticaError("桥接未启用或 URL / Token 未配置")
        headers = self._headers()
        headers["X-Workspace-ID"] = self._workspace_id
        try:
            async with aiohttp.ClientSession(trust_env=False) as session:
                async with session.request(
                    method,
                    self._api_url + path,
                    headers=headers,
                    json=payload,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=20),
                    allow_redirects=False,
                ) as response:
                    if not 200 <= response.status < 300:
                        labels = {
                            401: "Token 认证失败",
                            403: "没有调用权限",
                            404: "接口或会话不存在，请检查 Multica 版本",
                        }
                        raise MulticaError(
                            labels.get(
                                response.status, f"Multica HTTP {response.status}"
                            ),
                            response.status,
                            method != "GET" and response.status >= 500,
                        )
                    if response.status == 204:
                        return {}
                    return await response.json()
        except MulticaError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
            raise MulticaError(
                "Multica 请求失败，请检查连接；未自动重发", uncertain=method != "GET"
            ) from exc

    async def resolve_workspace(self) -> str:
        try:
            await self._ensure_workspace_id()
        except Exception as exc:
            raise MulticaError("无法读取工作区，请检查连接和工作区配置") from exc
        if not self._workspace_id:
            raise MulticaError("没有可用工作区")
        return self._workspace_id

    async def list_agents(self) -> list[dict]:
        await self.resolve_workspace()
        result = await self._request("GET", "/api/agents")
        if not isinstance(result, list):
            raise MulticaError("智能体列表格式不兼容")
        return [
            a
            for a in result
            if isinstance(a, dict) and a.get("id") and not a.get("archived_at")
        ]

    async def create_chat(
        self, agent_id: str, title: str, project_id: str = ""
    ) -> dict:
        await self.resolve_workspace()
        payload = {"agent_id": agent_id, "title": title}
        if project_id:
            payload["project_id"] = project_id
        return await self._object("POST", "/api/chat/sessions", payload)

    @staticmethod
    def _chat_path(session_id: str) -> str:
        return "/api/chat/sessions/" + quote(session_id, safe="")

    async def _object(
        self, method: str, path: str, payload: dict | None = None
    ) -> dict:
        result = await self._request(method, path, payload)
        if not isinstance(result, dict):
            raise MulticaError("Multica 响应格式不兼容", uncertain=method != "GET")
        return result

    async def get_chat(self, session_id: str) -> dict:
        return await self._object("GET", self._chat_path(session_id))

    async def send_chat(self, session_id: str, content: str) -> dict:
        result = await self._object(
            "POST", self._chat_path(session_id) + "/messages", {"content": content}
        )
        if not result.get("message_id") or not result.get("task_id"):
            raise MulticaError(
                "提交结果不完整，请到 Multica 核对，未自动重发", uncertain=True
            )
        return result

    async def messages(self, session_id: str, since_id: str = "") -> list[dict]:
        """Walk backwards from the latest page until reaching the durable cursor."""
        path = self._chat_path(session_id) + "/messages/page"
        params: dict[str, Any] = {"limit": 100}
        collected: list[dict] = []
        for _ in range(30):
            try:
                page = await self._request("GET", path, params=params)
            except MulticaError as exc:
                if exc.status != 404:
                    raise
                legacy = await self._request(
                    "GET", self._chat_path(session_id) + "/messages"
                )
                if not isinstance(legacy, list):
                    raise MulticaError("历史消息格式不兼容") from exc
                return self._after(legacy, since_id)
            if not isinstance(page, dict) or not isinstance(page.get("messages"), list):
                raise MulticaError("历史消息格式不兼容")
            messages = page["messages"]
            collected = messages + collected
            if not page.get("has_more") or any(
                m.get("id") == since_id for m in messages
            ):
                return self._after(collected, since_id)
            cursor = page.get("next_cursor") or {}
            if not cursor.get("id") or not cursor.get("created_at"):
                raise MulticaError("消息分页游标缺失")
            params.update(
                before_id=cursor["id"], before_created_at=cursor["created_at"]
            )
        raise MulticaError("未读消息过多，请在 Multica 查看后使用 /multica new")

    @staticmethod
    def _after(messages: list[dict], since_id: str) -> list[dict]:
        if since_id:
            for index, message in enumerate(messages):
                if message.get("id") == since_id:
                    return messages[index + 1 :]
        return messages

    async def pending(self, session_id: str) -> dict:
        return await self._object("GET", self._chat_path(session_id) + "/pending-task")

    async def stop(self, session_id: str) -> None:
        pending = await self.pending(session_id)
        await self._request("DELETE", self._chat_path(session_id) + "/queued-tasks")
        if pending.get("task_id"):
            await self._request(
                "POST", "/api/tasks/" + quote(pending["task_id"], safe="") + "/cancel"
            )
