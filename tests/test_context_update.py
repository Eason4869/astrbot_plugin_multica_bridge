import pytest
from astrbot_plugin_multica_bridge.multica_client import MulticaClient


def test_explicit_bad_workspace_never_falls_back():
    client = MulticaClient({"workspace_id": "typo"})
    with pytest.raises(ValueError):
        client._pick_workspace([{"id": "production", "slug": "prod"}])


def test_multiple_workspaces_require_explicit_selection():
    with pytest.raises(ValueError):
        MulticaClient({})._pick_workspace([{"id": "a"}, {"id": "b"}])


def test_unique_project_name_resolves_and_duplicate_does_not():
    client = MulticaClient({})
    assert (
        client.find_project("前端重构", [{"id": "p1", "title": "前端重构"}])["id"]
        == "p1"
    )
    with pytest.raises(ValueError):
        client.find_project(
            "前端重构",
            [{"id": "p1", "title": "前端重构"}, {"id": "p2", "title": "前端重构"}],
        )


def test_workspace_change_clears_old_project_without_mutating_input():
    from astrbot_plugin_multica_bridge.multica_client import apply_context_update

    current = {"workspace_id": "a", "project_id": "old", "token": "secret"}
    updated = apply_context_update(current, {"workspace_id": "b"}, [{"id": "b"}], [])
    assert updated["project_id"] == ""
    assert current["project_id"] == "old"


def test_cross_workspace_project_is_rejected():
    from astrbot_plugin_multica_bridge.multica_client import apply_context_update

    with pytest.raises(ValueError):
        apply_context_update(
            {"workspace_id": "a"},
            {"workspace_id": "b", "project_id": "p1"},
            [{"id": "b"}],
            [{"id": "p1", "workspace_id": "a"}],
        )


def test_ambiguous_id_prefix_does_not_choose_first():
    with pytest.raises(ValueError):
        MulticaClient({}).find_project(
            "12345678", [{"id": "12345678-1"}, {"id": "12345678-2"}]
        )


def test_project_selection_resolves_single_automatic_workspace():
    from astrbot_plugin_multica_bridge.multica_client import apply_context_update

    result = apply_context_update(
        {"workspace_id": "", "project_id": ""},
        {"project_id": "p1"},
        [{"id": "ws1", "slug": "demo"}],
        [{"id": "p1", "workspace_id": "ws1"}],
    )
    assert result["workspace_id"] == "ws1" and result["project_id"] == "p1"
