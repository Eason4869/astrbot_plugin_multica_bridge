"""AstrBot NL orchestration, bounded Provider parsing and confirmed Issue writes."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import re
import time
from datetime import datetime

from .actions import NL_ACTIONS, ActionRequest, authorize_action, dispatch_action
from .multica_client import PERMISSION_DENIED, MulticaClient, resolve_unique_resource
from .pending_intents import PendingIntentStore
from .session_store import connection_key, conversation_key
from .structured_nl import (
    LLM_PROMPT,
    SHANGHAI,
    parse_control_request,
    request_from_llm_payload,
    safe_control_text,
    validate_action_fields,
)

NL_TIMEOUT = 10


def owner_key(event) -> tuple[str, ...]:
    return (
        str(event.get_platform_id()),
        str(event.get_self_id()),
        conversation_key(event),
        str(event.get_sender_id()),
    )


def context_key(plugin, event) -> str:
    service = getattr(plugin, "_work_mode", None)
    state = service.store.get(conversation_key(event)) if service else {}
    raw = [
        connection_key(plugin.cfg),
        state.get("session_id"),
        state.get("generation"),
        plugin.cfg.get("multica_whitelist", []),
    ]
    return hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()


def pending_store(plugin) -> PendingIntentStore:
    if not hasattr(plugin, "_pending_intents"):
        plugin._pending_intents = PendingIntentStore()
    return plugin._pending_intents


async def handle_natural_language(plugin, event) -> None:
    from .nl_control import _looks_like_control_query, contains_keyword, strip_keyword

    text = str(event.message_str or "").strip()
    if not text or text.startswith("/"):
        return
    service = getattr(plugin, "_work_mode", None)
    if (
        service
        and service.store.get(conversation_key(event)).get("active")
        and service.should_route(event)
    ):
        return
    cfg = plugin.cfg
    confirmation = re.fullmatch(r"(确认|取消)\s+(\d{6})", text)
    keyword = str(cfg.get("nl_keyword") or "multica")
    if not confirmation and not contains_keyword(text, keyword):
        return
    if not cfg.get("enabled", True) or not cfg.get("nl_enabled", True):
        return
    if not plugin._chat_allowed(event):
        await plugin._reply(event, PERMISSION_DENIED)
        event.stop_event()
        return
    try:
        if confirmation:
            store = pending_store(plugin)
            if confirmation[1] == "取消":
                result = store.cancel(owner_key(event), confirmation[2])
                await plugin._reply(
                    event, "已取消草稿。" if result else "草稿不存在或已失效。"
                )
            else:
                request = store.claim(
                    owner_key(event),
                    confirmation[2],
                    context_key(plugin, event),
                    time.monotonic(),
                )
                if request is None:
                    await plugin._reply(event, "草稿不存在或已失效，请重新发起。")
                else:
                    await dispatch_action(plugin, event, request)
            event.stop_event()
            return
        result = parse_control_request(text, keyword)
        if result.status == "clarify":
            await plugin._reply(event, result.question)
            event.stop_event()
            return
        request = result.request
        if (
            request is None
            and cfg.get("nl_llm_enabled", True)
            and _looks_like_control_query(strip_keyword(text, keyword))
        ):
            request = await plugin._llm_parse_intent(event, text, keyword)
        if request is None:
            return
        await dispatch_action(plugin, event, request)
        event.stop_event()
    except (ValueError, RuntimeError) as exc:
        await plugin._reply(event, str(exc))
        event.stop_event()
    except Exception as exc:
        plugin.log.warning(
            "[multica_bridge] NL stage=dispatch exception=%s", type(exc).__name__
        )
        await plugin._reply(
            event, "本次操作未完成，请核对 Multica 后重试；未自动重发。"
        )
        event.stop_event()


async def parse_with_provider(
    plugin, event, text: str, keyword: str
) -> ActionRequest | None:
    if (
        not plugin.cfg.get("enabled", True)
        or not plugin.cfg.get("nl_enabled", True)
        or not plugin.cfg.get("nl_llm_enabled", True)
    ):
        return None
    if not safe_control_text(text) or not plugin._chat_allowed(event):
        return None
    allowed = [
        name for name in sorted(NL_ACTIONS) if authorize_action(plugin, event, name)
    ]
    if not allowed:
        return None
    window = conversation_key(event)
    user = (
        str(event.get_platform_id()),
        str(event.get_self_id()),
        str(event.get_sender_id()),
    )
    if not hasattr(plugin, "_nl_busy"):
        plugin._nl_busy, plugin._nl_last = set(), {}
    now = time.monotonic()
    if window in plugin._nl_busy or now - plugin._nl_last.get(user, -100) < 5:
        return None
    plugin._nl_busy.add(window)
    plugin._nl_last = {k: v for k, v in plugin._nl_last.items() if now - v < 5}
    plugin._nl_last[user] = now

    async def generate():
        from .nl_control import extract_json_object, extract_llm_reply_text

        origin = event.unified_msg_origin
        provider = None
        getter = getattr(plugin.context, "get_using_provider_async", None)
        if callable(getter):
            args = (origin,)
            try:
                inspect.signature(getter).bind(*args)
            except TypeError:
                args = ()
            provider = await getter(*args)
        if provider is None:
            getter = getattr(plugin.context, "get_using_provider", None)
            if callable(getter):
                provider = getter(origin)
        if provider is None or not callable(getattr(provider, "text_chat", None)):
            return None
        prompt = json.dumps(
            {
                "message": text,
                "keyword": keyword,
                "allowed_actions": allowed,
                "today": datetime.now(SHANGHAI).date().isoformat(),
                "timezone": "Asia/Shanghai",
            },
            ensure_ascii=False,
        )
        kwargs = {"prompt": prompt, "system_prompt": LLM_PROMPT}
        try:
            inspect.signature(provider.text_chat).bind(**kwargs)
        except TypeError:
            kwargs = {"prompt": LLM_PROMPT + "\n" + prompt}
        response = await provider.text_chat(**kwargs)
        payload = extract_json_object(extract_llm_reply_text(response))
        request = request_from_llm_payload(payload)
        if request and request.name not in allowed:
            return None
        if (
            request
            and request.name == "work_enter"
            and not re.search(r"进入|切换|切到|转到|开启|打开|启用|开始", text)
        ):
            return None
        return request

    try:
        return await asyncio.wait_for(generate(), NL_TIMEOUT)
    except Exception as exc:
        plugin.log.warning(
            "[multica_bridge] NL stage=provider exception=%s elapsed=%.2fs",
            type(exc).__name__,
            time.monotonic() - now,
        )
        return None
    finally:
        plugin._nl_busy.discard(window)


async def prepare_issue(plugin, fields: dict) -> tuple[MulticaClient, dict]:
    fields = validate_action_fields("issue_create", fields)
    client = MulticaClient(dict(plugin.cfg))
    await client._ensure_workspace_id()
    resolved = dict(fields)
    project = str(fields.get("project") or plugin.cfg.get("project_id") or "")
    if project:
        result = await client.list_projects()
        if not result["ok"]:
            raise ValueError("无法读取目标项目，请检查连接与权限")
        selected = resolve_unique_resource(project, result["projects"], "title")
        if (
            selected.get("workspace_id")
            and str(selected["workspace_id"]) != client._workspace_id
        ):
            raise ValueError("项目不属于目标工作区")
        resolved["project"] = str(selected["id"])
    if fields.get("assignee"):
        names = await client.resolve_assignee_names()
        selected = resolve_unique_resource(
            str(fields["assignee"]),
            [{"id": k, "name": v} for k, v in names.items()],
            "name",
        )
        resolved["assignee"] = str(selected["id"])
    return client, resolved


async def handle_issue_request(plugin, event, request: ActionRequest) -> None:
    key = context_key(plugin, event)
    fields = dict(request.fields)
    expected_workspace = fields.pop("_workspace_id", None)
    client, fields = await prepare_issue(plugin, fields)
    if key != context_key(plugin, event) or not authorize_action(
        plugin, event, "issue_create"
    ):
        raise ValueError("配置或权限已变化，请重新发起")
    if request.source != "confirmation":
        fields["_workspace_id"] = client._workspace_id
        code = pending_store(plugin).create(
            owner_key(event),
            ActionRequest("issue_create", fields),
            key,
            time.monotonic(),
        )
        preview = "\n".join(
            f"{name}：{value}"
            for name, value in fields.items()
            if not name.startswith("_")
        )
        await plugin._reply(
            event,
            f"待创建 Issue（尚未提交）\n工作区：{client._workspace_id}\n项目：{fields.get('project') or '工作区默认'}\n{preview}\n120 秒内由本人回复：确认 {code}\n取消：取消 {code}",
        )
        return
    if expected_workspace != client._workspace_id:
        raise ValueError("目标工作区已变化，请重新发起")
    result = await client.create_issue(
        title=fields["title"],
        description=fields.get("description", ""),
        priority=fields.get("priority", ""),
        status=fields.get("status", ""),
        labels=fields.get("labels", []),
        due_date=fields.get("due_date", ""),
        assignee_id=fields.get("assignee", ""),
        project_id=fields.get("project", ""),
    )
    await plugin._reply(
        event,
        ("✅ " if result["ok"] else "提交未确认，请在 Multica 核对；未自动重发。")
        + (result["message"] if result["ok"] else ""),
    )
