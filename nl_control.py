"""Multica 自然语言意图解析。

规则解析为主：识别「multica 建个issue：修复登录，优先级高」这类口语；
复杂句可选交给 AstrBot LLM 回退解析。输出统一为 ``NLIntent``，
再由 ``main.py`` 复用既有子指令实现，不重复调 Multica API。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

VALID_ACTIONS = {
    "help",
    "status",
    "inbox",
    "issue_create",
    "workspace_list",
    "workspace_select",
    "workspace_create",
    "project_list",
    "project_select",
    "project_create",
}

_PRIORITY_TOKENS = (
    (r"紧急|urgent|p0", "urgent"),
    (r"高|high|p1", "high"),
    (r"中|普通|medium|normal|p2", "medium"),
    (r"低|low|p3", "low"),
)

_STATUS_TOKENS = (
    (r"in[_\s-]?review|评审|待评审", "in_review"),
    (r"in[_\s-]?progress|进行中|处理中", "in_progress"),
    (r"backlog|待整理|池子里|需求池", "backlog"),
    (r"todo|待办|待处理", "todo"),
    (r"done|已完成|完成", "done"),
    (r"cancelled|canceled|已取消|取消", "cancelled"),
)

_DATE_RE = re.compile(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})日?")
_NOISE_PREFIXES = (
    "帮我",
    "麻烦",
    "请",
    "能不能",
    "可以",
    "需要",
    "我想",
    "我要",
    "用",
    "通过",
    "使用",
)

# 可直接映射到既有子指令的「指令风格」尾巴
_CMD_TAIL = re.compile(
    r"^(?P<head>help|status|inbox|h|帮助|状态|收件箱)\b",
    re.IGNORECASE,
)

_ISSUE_CMD = re.compile(
    r"^(?:issue|议题|任务)\s*(?:create|新建|创建)\s*(?P<body>.*)$",
    re.IGNORECASE | re.DOTALL,
)
_WORKSPACE_CMD = re.compile(
    r"^(?:workspace|工作区)\s*(?P<op>list|select|create|列表|选择|切换|新建)\s*(?P<body>.*)$",
    re.IGNORECASE | re.DOTALL,
)
_PROJECT_CMD = re.compile(
    r"^(?:project|项目)\s*(?P<op>list|select|create|列表|选择|切换|新建)\s*(?P<body>.*)$",
    re.IGNORECASE | re.DOTALL,
)

_ISSUE_NL = re.compile(
    r"^(?:要)?(?P<verb>建|新建|创建|开|提|提交|加)(?:一个|个|一条|条)?"
    r"(?:新的|新)?\s*(?P<kind>issue|议题|任务|ticket)\s*"
    r"(?P<sep>[:：]|\s)?\s*(?P<body>.*)$",
    re.IGNORECASE | re.DOTALL,
)

_WS_SELECT = re.compile(
    r"^(?:切换|选择|切到|换到|换|用)\s*(?:到|至)?\s*"
    r"(?P<kind>workspace|工作区)\s*(?P<target>.*)$",
    re.IGNORECASE | re.DOTALL,
)
_WS_CREATE = re.compile(
    r"^(?:建|新建|创建|开)(?:一个|个)?\s*"
    r"(?:新的|新)?\s*(?P<kind>workspace|工作区)\s*"
    r"(?P<sep>[:：]|\s)?\s*(?P<body>.*)$",
    re.IGNORECASE | re.DOTALL,
)
_WS_LIST = re.compile(
    r"^(?:看看|查看|列出|浏览|显示)?\s*"
    r"(?:所有|全部)?\s*(?P<kind>workspace|工作区)\s*"
    r"(?:列表|清单|list)?$",
    re.IGNORECASE,
)

_PROJ_SELECT = re.compile(
    r"^(?:切换|选择|切到|换到|换|用)\s*(?:到|至)?\s*"
    r"(?P<kind>project|项目)\s*(?P<target>.*)$",
    re.IGNORECASE | re.DOTALL,
)
_PROJ_CREATE = re.compile(
    r"^(?:建|新建|创建|开)(?:一个|个)?\s*"
    r"(?:新的|新)?\s*(?P<kind>project|项目)\s*"
    r"(?P<sep>[:：]|\s)?\s*(?P<body>.*)$",
    re.IGNORECASE | re.DOTALL,
)
_PROJ_LIST = re.compile(
    r"^(?:看看|查看|列出|浏览|显示)?\s*"
    r"(?:所有|全部)?\s*(?P<kind>project|项目)\s*"
    r"(?:列表|清单|list)?$",
    re.IGNORECASE,
)

_HELP_HINTS = re.compile(r"(帮助|help|指令|命令|用法|怎么用|怎么操作)", re.IGNORECASE)
_STATUS_HINTS = re.compile(r"(状态|status|连接|连通|通不通|能不能连)", re.IGNORECASE)
_INBOX_HINTS = re.compile(
    r"(收件箱|inbox|issue列表|议题列表|任务列表|看看issue|查看issue|"
    r"看看议题|查看议题|最近的?issue|最新issue|有哪些issue|有什么issue)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class NLIntent:
    """解析出的自然语言意图。``args`` 对应既有子指令的参数串。"""

    action: str
    args: str = ""
    source: str = "rule"  # rule | llm
    matched: bool = True

    @property
    def valid(self) -> bool:
        return self.matched and self.action in VALID_ACTIONS


def contains_keyword(text: str, keyword: str = "multica") -> bool:
    """消息是否包含触发关键词（默认 multica，不区分大小写）。"""
    kw = (keyword or "").strip()
    if not kw:
        return False
    return bool(
        re.search(
            r"(?<![a-zA-Z0-9_])" + re.escape(kw) + r"(?![a-zA-Z0-9_])",
            text or "",
            re.IGNORECASE,
        )
    )


def strip_keyword(text: str, keyword: str = "multica") -> str:
    """去掉关键词与常见前后缀噪声，留下待解析的意图正文。"""
    kw = (keyword or "multica").strip()
    t = text or ""
    if kw:
        t = re.sub(
            r"^(\s*(?:(?:请|帮我|用|使用|看看|列出|查看|查询)[\s，,：:]*)*)"
            + re.escape(kw)
            + r"(?![a-zA-Z0-9_])",
            r"\1 ",
            t,
            count=1,
            flags=re.IGNORECASE,
        )
    t = re.sub(r"^[\s、,，。.！!？?：:；;~～\-—]+", "", t)
    t = re.sub(r"[\s、,，。.！!？?：:；;~～]+$", "", t)
    t = t.strip()
    # 去掉开头的「帮我 / 请 / 用」等噪声，循环处理叠词
    changed = True
    while changed:
        changed = False
        for p in _NOISE_PREFIXES:
            if t.lower().startswith(p) and len(t) > len(p):
                t = t[len(p) :].lstrip(" ，,、：:")
                changed = True
    return t.strip()


def _norm_priority(raw: str) -> str:
    token = (raw or "").strip().lower()
    if not token:
        return ""
    for pattern, value in _PRIORITY_TOKENS:
        if re.fullmatch(pattern, token, re.IGNORECASE):
            return value
    # 允许「优先级高」这种粘连：取第一个命中的词
    for pattern, value in _PRIORITY_TOKENS:
        if re.search(pattern, token, re.IGNORECASE):
            return value
    return token


def _norm_status(raw: str) -> str:
    token = (raw or "").strip().lower().replace(" ", "_")
    if not token:
        return ""
    for pattern, value in _STATUS_TOKENS:
        if re.fullmatch(pattern, token, re.IGNORECASE):
            return value
    for pattern, value in _STATUS_TOKENS:
        if re.search(pattern, token, re.IGNORECASE):
            return value
    return token


def _format_date(match: re.Match[str]) -> str:
    y, m, d = match.group(1), int(match.group(2)), int(match.group(3))
    return f"{y}-{m:02d}-{d:02d}"


def _extract_issue_fields(body: str) -> dict[str, str]:
    """从口语正文抽取 issue 字段，剩余部分作为标题。"""
    text = body or ""
    out: dict[str, str] = {
        "title": "",
        "desc": "",
        "priority": "",
        "status": "",
        "labels": "",
        "due": "",
        "assignee": "",
        "project": "",
    }

    # 显式 flag 段优先（兼容 multica issue create xxx --priority 高）
    flag_re = re.compile(
        r"(--desc|--priority|--status|--assignee|--project|--due|--labels)\s+"
        r"((?:(?!--[a-zA-Z]).)*)"
    )
    flags = {m.group(1): m.group(2).strip() for m in flag_re.finditer(text)}
    residual = flag_re.sub(" ", text)

    if flags.get("--desc"):
        out["desc"] = flags["--desc"]
    if flags.get("--priority"):
        out["priority"] = _norm_priority(flags["--priority"])
    if flags.get("--status"):
        out["status"] = _norm_status(flags["--status"])
    if flags.get("--due"):
        out["due"] = flags["--due"].strip()
    if flags.get("--assignee"):
        out["assignee"] = flags["--assignee"].strip()
    if flags.get("--project"):
        out["project"] = flags["--project"].strip()
    if flags.get("--labels"):
        out["labels"] = flags["--labels"].replace("，", ",").strip()

    residual = residual.strip()
    # 中文/英文字段口语
    patterns = [
        (
            r"(?:描述|说明|desc|description)\s*[:：]?\s*(.+?)(?=\s+(?:优先级|状态|标签|截止|指派|assignee|priority|status|labels|due)\b|$)",
            "desc",
        ),
        (
            r"(?:优先级|priority)\s*[:：]?\s*(紧急|高|中|低|普通|urgent|high|medium|normal|low|p[0-3])",
            "priority",
        ),
        (
            r"(?:状态|status)\s*[:：]?\s*(in[_\s-]?review|in[_\s-]?progress|backlog|todo|done|cancelled|canceled|评审|待评审|进行中|处理中|待整理|待办|已完成|完成|已取消|取消)",
            "status",
        ),
        (r"(?:标签|labels?)\s*[:：]?\s*([^，,。.]+(?:[，,][^，,。.]+)*)", "labels"),
        (
            r"(?:截止|到期|due(?:\s*date)?)\s*[:：]?\s*(20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}日?)",
            "due",
        ),
        (r"(?:指派给|指派|assignee)\s*[:：]?\s*(\S+)", "assignee"),
        (r"(?:项目|project)\s*[:：]?\s*(\S+)", "project"),
        (
            r"(?:标题|title)\s*[:：]?\s*(.+?)(?=\s+(?:描述|优先级|状态|标签|截止|指派|desc|priority|status|labels|due|assignee)\b|$)",
            "title",
        ),
    ]

    consumed: list[str] = []
    for pattern, key in patterns:
        if out.get(key):
            continue
        m = re.search(pattern, residual, re.IGNORECASE)
        if not m:
            continue
        value = m.group(1).strip()
        if key == "priority":
            value = _norm_priority(value)
        elif key == "status":
            value = _norm_status(value)
        elif key == "due":
            dm = _DATE_RE.search(value)
            value = _format_date(dm) if dm else value
        elif key == "labels":
            value = value.replace("，", ",").strip()
        out[key] = value
        consumed.append(m.group(0))

    for piece in consumed:
        residual = residual.replace(piece, " ", 1)

    # 口语标点：「修复登录，优先级高」里的逗号句子
    # 再扫一遍“，优先级高 / 描述xxx”
    for pattern, key in (
        (r"[，,]\s*优先级\s*(紧急|高|中|低|普通|urgent|high|medium|low)", "priority"),
        (r"[，,]\s*描述\s*(.+)$", "desc"),
        (r"[，,]\s*状态\s*(\S+)", "status"),
        (r"[，,]\s*标签\s*([^，,]+)", "labels"),
    ):
        if out.get(key):
            continue
        m = re.search(pattern, residual, re.IGNORECASE)
        if not m:
            continue
        value = m.group(1).strip()
        if key == "priority":
            value = _norm_priority(value)
        elif key == "status":
            value = _norm_status(value)
        out[key] = value
        residual = residual.replace(m.group(0), " ", 1)

    residual = re.sub(r"\s+", " ", residual).strip(" ，,、：:：.。")
    if not out["title"]:
        out["title"] = residual
    elif residual and residual not in out["title"]:
        # 标题字段与剩余文本合并，避免丢信息
        out["title"] = f"{out['title']} {residual}".strip()
    return out


def _issue_fields_to_args(fields: dict[str, str]) -> str:
    """把抽取字段拼回 ``_cmd_issue_create`` 可解析的参数串。"""
    title = (fields.get("title") or "").strip()
    parts = [title] if title else []
    if fields.get("desc"):
        parts.append(f"--desc {fields['desc']}")
    if fields.get("priority"):
        parts.append(f"--priority {fields['priority']}")
    if fields.get("status"):
        parts.append(f"--status {fields['status']}")
    if fields.get("assignee"):
        parts.append(f"--assignee {fields['assignee']}")
    if fields.get("project"):
        parts.append(f"--project {fields['project']}")
    if fields.get("due"):
        parts.append(f"--due {fields['due']}")
    if fields.get("labels"):
        parts.append(f"--labels {fields['labels']}")
    return " ".join(parts).strip()


def _looks_like_control_query(remainder: str) -> bool:
    """是否像在下发控制指令，而不是「multica是什么」这类闲聊。"""
    r = remainder or ""
    if not r:
        return False
    if _ISSUE_CMD.match(r) or _WORKSPACE_CMD.match(r) or _PROJECT_CMD.match(r):
        return True
    if _CMD_TAIL.match(r):
        return True
    if _ISSUE_NL.match(r) or _WS_SELECT.match(r) or _WS_CREATE.match(r):
        return True
    if _PROJ_SELECT.match(r) or _PROJ_CREATE.match(r):
        return True
    if _WS_LIST.match(r) or _PROJ_LIST.match(r):
        return True
    if _HELP_HINTS.search(r) or _STATUS_HINTS.search(r) or _INBOX_HINTS.search(r):
        return True
    control_words = (
        "建",
        "创建",
        "新建",
        "切换",
        "选择",
        "列出",
        "查看",
        "看看",
        "收件箱",
        "inbox",
        "issue",
        "议题",
        "任务",
        "工作区",
        "项目",
        "workspace",
        "project",
        "帮助",
        "状态",
        "help",
        "status",
    )
    low = r.casefold()
    return any(w.casefold() in low for w in control_words)


def parse_nl_intent(text: str, keyword: str = "multica") -> NLIntent | None:
    """规则解析自然语言 / 无斜杠指令。无法识别时返回 None。"""
    if not contains_keyword(text, keyword):
        return None
    body = strip_keyword(text, keyword)
    if not body:
        # 仅提到 multica，没有动作
        return None
    if not _looks_like_control_query(body):
        return None

    # 1) 指令风格（multica status / multica issue create ...）
    m = _ISSUE_CMD.match(body)
    if m:
        args = _issue_fields_to_args(_extract_issue_fields(m.group("body").strip()))
        return NLIntent("issue_create", args)

    m = _WORKSPACE_CMD.match(body)
    if m:
        op = m.group("op").lower()
        target = (m.group("body") or "").strip()
        if op in ("list", "列表"):
            return NLIntent("workspace_list")
        if op in ("select", "选择", "切换"):
            return NLIntent("workspace_select", target)
        if op in ("create", "新建"):
            args = _project_or_ws_create_args(target, ("--slug", "--desc", "--context"))
            return NLIntent("workspace_create", args)
        return None

    m = _PROJECT_CMD.match(body)
    if m:
        op = m.group("op").lower()
        target = (m.group("body") or "").strip()
        if op in ("list", "列表"):
            return NLIntent("project_list")
        if op in ("select", "选择", "切换"):
            return NLIntent("project_select", target)
        if op in ("create", "新建"):
            args = _project_or_ws_create_args(target, ("--desc",))
            return NLIntent("project_create", args)
        return None

    m = _CMD_TAIL.match(body)
    if m:
        token = m.group("head").lower()
        rest = body[m.end() :].strip()
        if token in ("help", "帮助", "h"):
            return NLIntent("help")
        if token in ("status", "状态"):
            return NLIntent("status")
        if token in ("inbox", "收件箱"):
            return NLIntent("inbox", _normalize_inbox_args(rest))
        return None

    # 2) 口语：建 issue / 切换项目 / 收件箱 等
    m = _ISSUE_NL.match(body)
    if m:
        args = _issue_fields_to_args(
            _extract_issue_fields((m.group("body") or "").strip())
        )
        return NLIntent("issue_create", args)

    m = _WS_CREATE.match(body)
    if m:
        args = _project_or_ws_create_args(
            (m.group("body") or "").strip(), ("--slug", "--desc", "--context")
        )
        return NLIntent("workspace_create", args)

    m = _WS_SELECT.match(body)
    if m:
        target = (m.group("target") or "").strip(" ，,、：:")
        # 「切换到工作区」后面可能再跟「列表」等误匹配，交给 select 空参提示
        return NLIntent("workspace_select", target)

    if _WS_LIST.match(body) or re.search(
        r"工作区\s*(列表|清单)|列出\s*工作区|有哪些\s*工作区", body
    ):
        return NLIntent("workspace_list")

    m = _PROJ_CREATE.match(body)
    if m:
        args = _project_or_ws_create_args((m.group("body") or "").strip(), ("--desc",))
        return NLIntent("project_create", args)

    m = _PROJ_SELECT.match(body)
    if m:
        target = (m.group("target") or "").strip(" ，,、：:")
        return NLIntent("project_select", target)

    if _PROJ_LIST.match(body) or re.search(
        r"项目\s*(列表|清单)|列出\s*项目|有哪些\s*项目", body
    ):
        return NLIntent("project_list")

    if _INBOX_HINTS.search(body):
        # 从正文抠出数量与 open/done
        cleaned = _INBOX_HINTS.sub(" ", body)
        return NLIntent("inbox", _normalize_inbox_args(cleaned))

    if _STATUS_HINTS.search(body):
        return NLIntent("status")

    if _HELP_HINTS.search(body):
        return NLIntent("help")

    return None


def _project_or_ws_create_args(body: str, flags: tuple[str, ...]) -> str:
    """把「名称 xxx --desc yyy」整理成指令参数串（缺 flag 时整段作名称）。"""
    body = (body or "").strip()
    if not body:
        return ""
    # 已是 flag 风格则原样返回
    if any(f in body.split() for f in flags):
        return body
    # 口语：名称 desc xxx / 描述 xxx
    name = body
    extra: list[str] = []
    desc_m = re.search(
        r"(?:描述|说明|desc|description)\s*[:：]?\s*(.+)$", body, re.IGNORECASE
    )
    if desc_m:
        extra.append(f"--desc {desc_m.group(1).strip()}")
        name = body[: desc_m.start()].strip(" ，,、：:")
    slug_m = re.search(r"(?:slug|标识)\s*[:：]?\s*(\S+)", body, re.IGNORECASE)
    if slug_m and "--slug" in flags:
        extra.append(f"--slug {slug_m.group(1)}")
        name = name.replace(slug_m.group(0), " ").strip(" ，,、：:")
    ctx_m = re.search(r"(?:背景|context)\s*[:：]?\s*(.+)$", body, re.IGNORECASE)
    if ctx_m and "--context" in flags:
        extra.append(f"--context {ctx_m.group(1).strip()}")
        name = re.sub(
            r"(?:背景|context)\s*[:：]?\s*.+$", "", name, flags=re.IGNORECASE
        ).strip(" ，,、：:")
    parts = [name, *extra]
    return " ".join(p for p in parts if p).strip()


def _normalize_inbox_args(raw: str) -> str:
    """把口语收件箱参数归一成 ``10 open`` 这类指令尾串。"""
    text = re.sub(r"[，,。.？?！!]", " ", raw or "")
    tokens: list[str] = []
    status = ""
    for tok in text.split():
        low = tok.lower()
        if "open" in low or "未完成" in tok or "进行中" in tok or "未结" in tok:
            status = "open"
        elif (
            "done" in low
            or "已完成" in tok
            or "完成" == tok.strip("的了啊呀")
            or "已取消" in tok
        ):
            status = "done"
        elif tok.isdigit():
            tokens.append(tok)
    if status:
        tokens.append(status)
    return " ".join(tokens)


LLM_SYSTEM_PROMPT = """你是 Multica 桥接插件的意图解析器。
只输出一个 JSON 对象，不要 Markdown 代码块，不要解释。
格式：{"action": "<action>", "args": "<args>"}

action 只能取：
help, status, inbox,
issue_create,
workspace_list, workspace_select, workspace_create,
project_list, project_select, project_create,
none

规则：
1. issue_create 的 args 使用既有指令参数，例如：
   修复登录失败 --desc 用户超时 --priority 高 --labels 后端
   优先级只写：紧急|高|中|低 或 urgent|high|medium|low
   状态只写：backlog|todo|in_progress|in_review|done|cancelled
2. workspace_select / project_select 的 args 是 id 或 slug/标题关键词。
3. inbox 的 args 是可选的数量与 open/done，例如 "10 open"。
4. workspace_create / project_create 的 args 是名称及可选 --desc / --slug / --context。
5. 如果用户只是在询问 Multica 是什么、闲聊，或无法构成明确控制意图，输出
   {"action":"none","args":""}。
"""


def extract_json_object(text: str) -> dict[str, Any] | None:
    """从模型回复中抠出第一个 JSON 对象。"""
    if not text:
        return None
    raw = text.strip()
    # 去掉 ```json ... ```
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL | re.IGNORECASE)
    if fence:
        raw = fence.group(1)
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def intent_from_llm_payload(data: dict[str, Any] | None) -> NLIntent | None:
    """把 LLM 返回的 JSON 规范成 NLIntent。"""
    if not data:
        return None
    action = str(data.get("action") or "").strip().lower()
    if action in ("", "none", "unknown"):
        return None
    if action not in VALID_ACTIONS:
        return None
    args = data.get("args")
    if args is None:
        args = ""
    elif not isinstance(args, str):
        args = str(args)
    if action == "inbox":
        args = _normalize_inbox_args(args)
    return NLIntent(action=action, args=args.strip(), source="llm")


def build_llm_prompt(message: str, keyword: str = "multica") -> str:
    body = strip_keyword(message, keyword)
    return (
        f"触发关键词：{keyword}\n"
        f"用户原始消息：{message}\n"
        f"去掉关键词后的正文：{body}\n"
        "请解析用户想要执行的 Multica 操作。"
    )


def extract_llm_reply_text(resp: Any) -> str:
    """兼容不同 AstrBot 版本的 LLMResponse 文本字段。"""
    for attr in (
        "completion_text",
        "result_completion",
        "result_str",
        "text",
        "content",
        "completion",
    ):
        value = getattr(resp, attr, None)
        if isinstance(value, str) and value.strip():
            return value
    if isinstance(resp, str):
        return resp
    return str(resp or "")


# Keep the existing rule/helper API available to integrations during migration.
from .structured_nl import (  # noqa: E402,F401
    ParseResult,
    parse_control_request,
    parse_work_enter,
    request_from_llm_payload,
    validate_action_fields,
)
