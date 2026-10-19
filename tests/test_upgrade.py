"""Old credentials must survive startup, incremental saves and reloads."""

import json

import pytest
from astrbot_plugin_multica_bridge import config

OLD = {
    "enabled": True,
    "api_url": "https://old.example.test/multica",
    "token": "old-working-secret",
    "workspace_id": "original-workspace",
    "project_id": "original-project",
    "group_chat_mode": "whitelist",
    "group_chat_list": ["123"],
    "unknown_legacy_setting": {"keep": True},
}


def test_upgrade_and_repeated_saves_preserve_original_credentials(tmp_path):
    path = tmp_path / "config.json"
    original = json.dumps(OLD, ensure_ascii=False).encode()
    path.write_bytes(original)
    loaded = config.deep_merge(
        config.CONFIG_DEFAULTS, config.load_plugin_config(str(tmp_path))
    )
    assert path.read_bytes() == original  # no startup migration write
    updated = config.merge_config_update(
        loaded, {"default_agent_id": "agent-1", "token": ""}
    )
    config.save_plugin_config(str(tmp_path), updated)
    reloaded = config.load_plugin_config(str(tmp_path))
    for key, value in OLD.items():
        assert reloaded[key] == value
    assert reloaded["default_agent_id"] == "agent-1"
    assert (tmp_path / "config.pre-work-mode.json").read_bytes() == original
    config.save_plugin_config(str(tmp_path), reloaded)
    assert (tmp_path / "config.pre-work-mode.json").read_bytes() == original


@pytest.mark.parametrize(
    "patch",
    [
        {"token": ""},
        {"token": "   "},
        {"token": None},
        {"token": "old-****cret"},
        {"api_url": ""},
        {"api_url": None},
        {"api_url": "  "},
    ],
)
def test_unmodified_credentials_are_never_cleared_by_settings(patch):
    updated = config.merge_config_update(OLD, patch)
    assert updated["api_url"] == OLD["api_url"]
    assert updated["token"] == OLD["token"]


def test_clear_token_is_explicit():
    assert config.merge_config_update(OLD, {"clear_token": True})["token"] == ""
    assert (
        config.merge_config_update(OLD, {"clear_token": "false"})["token"]
        == OLD["token"]
    )


@pytest.mark.parametrize("raw", [b'{"token":', b"[]", b"null"])
def test_invalid_old_config_is_not_replaced_with_defaults(tmp_path, raw):
    path = tmp_path / "config.json"
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        config.load_plugin_config(str(tmp_path))
    with pytest.raises(ValueError):
        config.save_plugin_config(str(tmp_path), config.CONFIG_DEFAULTS)
    assert path.read_bytes() == raw


def test_incomplete_runtime_snapshot_does_not_erase_disk_fields(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps(OLD), encoding="utf-8")
    config.save_plugin_config(str(tmp_path), {"default_agent_id": "agent-2"})
    assert config.load_plugin_config(str(tmp_path))["token"] == OLD["token"]


def test_atomic_save_retries_transient_windows_file_lock(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    original = config.os.replace
    attempts = []
    def locked_once(source, target):
        attempts.append(target)
        if len(attempts) < 3:
            raise PermissionError("Transient external file lock")
        original(source, target)
    monkeypatch.setattr(config.os, "replace", locked_once)
    config.atomic_json_write(str(path), {"active": True})
    assert json.loads(path.read_text())["active"]
    assert len(attempts) == 3
    assert not list(tmp_path.glob("*.tmp"))
