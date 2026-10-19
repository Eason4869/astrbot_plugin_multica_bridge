from datetime import datetime, timedelta, timezone

import pytest
from astrbot_plugin_multica_bridge import nl_control as nl

NOW = datetime(2026, 10, 19, 23, tzinfo=timezone(timedelta(hours=8)))


@pytest.mark.parametrize(
    "text",
    [
        "进入multica模式",
        "进入 multica 工作模式",
        "切换为multica工作",
        "切换到 Multica 工作模式",
        "切到multica模式",
        "转到multica工作模式",
        "multica，进入工作模式",
        "帮我进入 multica 工作模式",
    ],
)
def test_work_enter_variations_are_deterministic(text):
    result = nl.parse_work_enter(text, "multica")
    assert result.status == "executable"
    assert result.request.name == "work_enter"
    assert result.request.fields == {}


@pytest.mark.parametrize(
    "text",
    [
        "不要进入multica模式",
        "怎么切换为multica工作",
        "他说进入multica模式",
        "如果进入multica模式会怎样",
        "multica",
        "开始工作",
        "进入multica模式，然后执行任务",
        "notmultica status",
    ],
)
def test_non_requests_never_enter(text):
    result = nl.parse_control_request(text, now=NOW)
    assert not result.request or result.request.name != "work_enter"


def test_issue_body_keyword_is_preserved_and_relative_date_is_local():
    result = nl.parse_control_request(
        "multica 建个issue：multica 登录失败，截止明天", now=NOW
    )
    assert result.request.fields["title"] == "multica 登录失败"
    assert result.request.fields["due_date"] == "2026-10-20"


@pytest.mark.parametrize(
    "text",
    [
        "multica 创建项目 测试，先不要执行",
        "multica 建个issue：修复登录，然后切换项目 前端重构",
        "multica 建个issue：修复登录，截止2026-02-31",
    ],
)
def test_ambiguous_or_invalid_input_is_not_executable(text):
    assert nl.parse_control_request(text, now=NOW).status != "executable"


def test_spoken_inbox_count_is_not_lost():
    result = nl.parse_control_request("multica 收件箱最近五条未完成的", now=NOW)
    assert result.request.fields == {"count": 5, "status": "open"}


def test_model_payload_is_strict_and_cannot_invent_actions():
    for payload in [
        {"action": "issue_create", "fields": {"title": "x", "shell": "bad"}},
        {"action": "work_exit", "fields": {}},
        {"action": "inbox", "fields": {"count": "5"}},
    ]:
        with pytest.raises(ValueError):
            nl.request_from_llm_payload(payload, NOW)
