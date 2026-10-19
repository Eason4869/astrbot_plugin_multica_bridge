import asyncio
import importlib

import pytest
from astrbot_plugin_multica_bridge import nl_control as nl


@pytest.mark.parametrize(
    "result",
    [
        {"ok": True, "issues": []},
        {"ok": True, "issues": [{"id": "issue-one", "title": "修复登录"}]},
        {"ok": False, "message": "HTTP 403"},
    ],
)
def test_issue_list_uses_correct_name_for_results_empty_and_errors(
    nl_plugin, monkeypatch, result
):
    plugin, _, replies = nl_plugin
    client = importlib.import_module("astrbot_plugin_multica_bridge.multica_client")

    async def listing(self, **kwargs):
        return result

    async def names(self, ids):
        return {}

    monkeypatch.setattr(client.MulticaClient, "list_issues", listing)
    monkeypatch.setattr(client.MulticaClient, "resolve_assignee_names", names)
    asyncio.run(plugin._cmd_inbox(object(), ""))
    assert len(replies) == 1
    assert "Issue列表" in replies[0]
    assert "收件箱" not in replies[0]


@pytest.mark.parametrize("name", ["Issue列表", "issue列表", "收件箱", "inbox"])
def test_new_name_and_legacy_names_keep_query_arguments(name):
    result = nl.parse_control_request(f"multica {name} 5 open")
    assert result.status == "executable"
    assert result.request.name == "inbox"
    assert result.request.fields == {"count": 5, "status": "open"}
