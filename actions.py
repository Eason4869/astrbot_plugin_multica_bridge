"""Shared operation identities and command authorization for every entry point."""

from __future__ import annotations

from dataclasses import dataclass

ACTION_COMMANDS = {
    "help": "multica help",
    "status": "multica status",
    "inbox": "multica inbox",
    "issue_create": "multica issue create",
    "work_enter": "multica enter",
    "workspace_list": "multica workspace list",
    "workspace_select": "multica workspace select",
    "workspace_create": "multica workspace create",
    "project_list": "multica project list",
    "project_select": "multica project select",
    "project_create": "multica project create",
}
NL_ACTIONS = {"help", "status", "inbox", "issue_create", "work_enter"}
MAIN_COMMANDS = (
    ("/multica", "进入或恢复工作模式"),
    ("/multica exit", "退出工作模式，恢复普通机器人"),
    ("/multica new", "新建对话"),
    ("/multica agent [编号或ID]", "查看或切换智能体"),
    ("/multica stop", "停止执行，保持工作模式"),
    ("/multica status", "查看模式、连接和执行状态"),
    ("/multica help", "查看帮助"),
)


def help_text() -> str:
    return (
        "Multica 工作模式\n"
        + "\n".join(f"{cmd} — {desc}" for cmd, desc in MAIN_COMMANDS)
        + "\n\n高级功能：/multica inbox、/multica issue create\n兼容管理：workspace/project 的 list/select/create 仍可使用，默认工作区与项目全局生效，建议使用 WebUI 设置。\n自然语言：进入multica模式、切换为multica工作；创建 Issue 需本人确认。\n群聊仅开启者的文字转发；回复在群内可见。退出使用 /multica exit。"
    )


@dataclass(frozen=True)
class ActionRequest:
    name: str
    fields: dict[str, object]
    source: str = "rule"


def check_handler(handler, event, cfg: dict) -> bool:
    from astrbot.core.star.filter.command import CommandFilter
    from astrbot.core.star.filter.command_group import CommandGroupFilter

    if handler is None or not handler.enabled:
        return False
    for item in handler.event_filters:
        if isinstance(item, (CommandFilter, CommandGroupFilter)):
            if not item.custom_filter_ok(event, cfg):
                return False
        elif not item.filter(event, cfg):
            return False
    return True


def authorize_action(
    plugin, event, action_name: str, astrbot_cfg: dict | None = None
) -> bool:
    try:
        command = ACTION_COMMANDS.get(action_name)
        if (
            not command
            or not plugin.cfg.get("enabled", True)
            or not plugin._chat_allowed(event)
        ):
            return False
        if astrbot_cfg is None:
            astrbot_cfg = plugin.context.get_config(event.unified_msg_origin)
        return check_handler(
            plugin._find_work_handler(event, command), event, astrbot_cfg
        )
    except Exception:
        # Missing registries/configuration are not permission to execute.
        return False


async def dispatch_action(plugin, event, request: ActionRequest) -> None:
    if not plugin._chat_allowed(event):
        from .multica_client import PERMISSION_DENIED

        await plugin._reply(event, PERMISSION_DENIED)
        return
    if not authorize_action(plugin, event, request.name):
        await plugin._reply(event, "权限不足或指令已停用，无法执行此 Multica 操作。")
        return
    if request.source != "command" and request.name not in NL_ACTIONS:
        await plugin._reply(
            event,
            "工作区和项目管理请使用 WebUI → Multica桥接 → 设置；旧管理命令仍兼容。",
        )
        return
    args = str(request.fields.get("args") or "")
    if request.name == "work_enter":
        service = getattr(plugin, "_work_mode", None)
        if not service:
            await plugin._reply(event, "工作模式未就绪，请检查插件日志。")
            return
        await service.enter_from_intent(event)
        return
    if request.name == "issue_create" and request.source != "command":
        from .natural_language import handle_issue_request

        await handle_issue_request(plugin, event, request)
        return
    if request.name == "inbox" and "count" in request.fields:
        args = f"{request.fields['count']} {request.fields.get('status', '')}".strip()
    method = getattr(plugin, "_cmd_" + request.name, None)
    service = getattr(plugin, "_work_mode", None)
    if request.name == "status" and service:
        from .session_store import conversation_key

        if service.store.get(conversation_key(event)).get("session_id"):
            await service._status(event, conversation_key(event))
            return
    if method:
        if request.name in {"help", "status", "workspace_list", "project_list"}:
            await method(event)
        else:
            await method(event, args)
