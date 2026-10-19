import asyncio
import copy

import pytest
from astrbot_plugin_multica_bridge.multica_client import MulticaClient

SPACES = [
    {"id": "workspace-a", "name": "研发", "slug": "dev", "private": "secret"},
    {"id": "workspace-b", "name": "生产", "slug": "prod", "private": "secret"},
]


@pytest.mark.parametrize("selected", ["", "workspace-b", "removed-workspace"])
def test_connection_discovers_all_ids_without_selecting_or_changing_config(
    monkeypatch, selected
):
    cfg = {"workspace_id": selected, "token": "secret"}
    original = copy.deepcopy(cfg)
    calls = []

    async def listing(self):
        calls.append(True)
        return {"ok": True, "workspaces": SPACES}

    monkeypatch.setattr(MulticaClient, "list_workspaces", listing)
    result = asyncio.run(MulticaClient(cfg).test_connection())
    assert result["connected"] is True
    assert result["workspaces"] == [
        {k: item[k] for k in ("id", "name", "slug")} for item in SPACES
    ]
    assert result["workspace_selection_required"] is (selected != "workspace-b")
    assert result["ok"] is (selected == "workspace-b")
    assert result["workspace_id"] == (
        "workspace-b" if selected == "workspace-b" else None
    )
    assert cfg == original
    assert calls == [True]
    assert "secret" not in str(result)


def test_connection_failure_has_no_selectable_workspace(monkeypatch):
    async def listing(self):
        return {"ok": False, "message": "Token 无效", "workspaces": []}

    monkeypatch.setattr(MulticaClient, "list_workspaces", listing)
    result = asyncio.run(MulticaClient({}).test_connection())
    assert result["connected"] is False
    assert result["workspaces"] == []
    assert result["workspace_selection_required"] is False
    assert not result["ok"]


def test_single_workspace_remains_automatic_without_persisting(monkeypatch):
    async def listing(self):
        return {"ok": True, "workspaces": SPACES[:1]}

    monkeypatch.setattr(MulticaClient, "list_workspaces", listing)
    cfg = {"workspace_id": ""}
    result = asyncio.run(MulticaClient(cfg).test_connection())
    assert result["connected"] and result["ok"]
    assert result["workspace_id"] == "workspace-a"
    assert not result["workspace_selection_required"]
    assert cfg["workspace_id"] == ""
