"""核心逻辑单元测试（不依赖 AstrBot 运行时）。"""

from __future__ import annotations

from astrbot_plugin_multica_bridge import config
from astrbot_plugin_multica_bridge import multica_client as mc


class TestToBool:
    def test_passthrough_bool(self) -> None:
        assert config.to_bool(True) is True
        assert config.to_bool(False) is False

    def test_string_false_variants(self) -> None:
        for raw in ("false", "FALSE", "0", "no", "off", "否", "关"):
            assert config.to_bool(raw) is False, raw

    def test_string_true_variants(self) -> None:
        for raw in ("true", "1", "yes", "on", "是", "开"):
            assert config.to_bool(raw) is True, raw

    def test_numbers(self) -> None:
        assert config.to_bool(1) is True
        assert config.to_bool(0) is False

    def test_unknown_falls_back_to_default(self) -> None:
        assert config.to_bool("maybe", default=True) is True
        assert config.to_bool("maybe", default=False) is False
        assert config.to_bool(None, default=True) is True


class TestCoerce:
    def test_bool_default_rejects_string_false(self) -> None:
        # 回归：旧实现 bool("false") 会错误地变成 True
        assert config.coerce_to_default_type("false", True) is False

    def test_int_default_clamps_negative(self) -> None:
        assert config.coerce_to_default_type("-5", 0) == 0
        assert config.coerce_to_default_type("7", 0) == 7
        assert config.coerce_to_default_type("abc", 3) == 3

    def test_str_and_list(self) -> None:
        assert config.coerce_to_default_type(123, "") == "123"
        assert config.coerce_to_default_type(("a", "b"), []) == ["a", "b"]
        assert config.coerce_to_default_type("nope", []) == []

    def test_nested_dict(self) -> None:
        default = {"a": {"b": 1}}
        assert config.coerce_to_default_type({"a": {"b": "9"}}, default) == {"a": {"b": 9}}


class TestDeepMerge:
    def test_recursive_merge(self) -> None:
        base = {"a": 1, "n": {"x": 1, "y": 2}}
        out = config.deep_merge(base, {"n": {"y": 9}})
        assert out == {"a": 1, "n": {"x": 1, "y": 9}}
        # 不修改原对象
        assert base["n"]["y"] == 2

    def test_ignores_non_dict(self) -> None:
        assert config.deep_merge({"a": 1}, None, "x") == {"a": 1}


class TestMaskSecret:
    def test_empty(self) -> None:
        assert mc.mask_secret("") == "（未配置）"

    def test_short(self) -> None:
        assert mc.mask_secret("ab") == "****"
        assert mc.mask_secret("abcd") == "ab****"

    def test_long_keeps_head_and_tail(self) -> None:
        assert mc.mask_secret("abcdefghijkl") == "abcd****ijkl"


class TestChatAllowed:
    CFG = {
        "group_chat_mode": "blacklist",
        "group_chat_list": ["111"],
        "private_chat_mode": "whitelist",
        "private_chat_list": ["222"],
    }

    def test_blacklist(self) -> None:
        assert mc.check_chat_allowed(self.CFG, "group", "111") is False
        assert mc.check_chat_allowed(self.CFG, "group", "999") is True

    def test_whitelist(self) -> None:
        assert mc.check_chat_allowed(self.CFG, "private", "222") is True
        assert mc.check_chat_allowed(self.CFG, "private", "333") is False

    def test_disabled(self) -> None:
        cfg = dict(self.CFG, group_chat_mode="disabled")
        assert mc.check_chat_allowed(cfg, "group", "111") is True

    def test_invalid_cfg_is_permissive(self) -> None:
        assert mc.check_chat_allowed(None, "group", "1") is True


class TestWorkspaceLookup:
    WORKSPACES = [
        {"id": "d79e9419-0000-0000-0000-000000000001", "name": "A", "slug": "eason-service"},
        {"id": "11112222-0000-0000-0000-000000000002", "name": "B", "slug": "other"},
    ]

    def test_find_by_slug_case_insensitive(self) -> None:
        client = mc.MulticaClient({})
        assert client.find_workspace("EASON-SERVICE", self.WORKSPACES)["name"] == "A"

    def test_find_by_id_prefix(self) -> None:
        client = mc.MulticaClient({})
        assert client.find_workspace("11112222", self.WORKSPACES)["name"] == "B"

    def test_find_missing_returns_none(self) -> None:
        client = mc.MulticaClient({})
        assert client.find_workspace("nope", self.WORKSPACES) is None
        assert client.find_workspace("", self.WORKSPACES) is None

    def test_pick_prefers_configured_then_first(self) -> None:
        client = mc.MulticaClient({"workspace_id": "other"})
        _ws, name, _id = client._pick_workspace(self.WORKSPACES)
        assert name == "B"
        fallback = mc.MulticaClient({})
        assert fallback._pick_workspace(self.WORKSPACES)[1] == "A"


class TestProjectLookup:
    PROJECTS = [
        {"id": "e8a339ad-32ec-49ac-bbd7-0c8d7e1b1466", "title": "前端重构"},
    ]

    def test_find_project(self) -> None:
        client = mc.MulticaClient({})
        assert client.find_project("e8a339ad", self.PROJECTS)["title"] == "前端重构"
        assert client.find_project("deadbeef", self.PROJECTS) is None


class TestGetMulticaConfig:
    def test_defaults_are_filled(self) -> None:
        out = mc.get_multica_config({"token": "t"})
        assert out["token"] == "t"
        assert out["api_url"] == config.CONFIG_DEFAULTS["api_url"]
        assert out["enabled"] is True

    def test_non_dict_returns_defaults(self) -> None:
        assert mc.get_multica_config(None)["api_url"] == config.CONFIG_DEFAULTS["api_url"]
