"""自然语言意图解析测试（不依赖 AstrBot 运行时）。"""

from __future__ import annotations

from astrbot_plugin_multica_bridge import config
from astrbot_plugin_multica_bridge import nl_control as nl


class TestKeyword:
    def test_contains_case_insensitive(self) -> None:
        assert nl.contains_keyword("Multica 建个issue", "multica") is True
        assert nl.contains_keyword("看看MULTICA收件箱") is True
        assert nl.contains_keyword("今天天气不错") is False

    def test_strip_keyword_and_noise(self) -> None:
        body = nl.strip_keyword("帮我用multica建个issue：修复登录")
        assert "multica" not in body.lower()
        assert "issue" in body.lower()
        assert "建" in body


class TestParseRuleIntents:
    def test_issue_create_spoken(self) -> None:
        intent = nl.parse_nl_intent("multica 建个issue：修复登录失败，优先级高")
        assert intent is not None
        assert intent.action == "issue_create"
        assert "修复登录失败" in intent.args
        assert "--priority" in intent.args
        assert "high" in intent.args

    def test_issue_create_with_flags(self) -> None:
        intent = nl.parse_nl_intent(
            "multica issue create 修复登录 --desc 超时 --priority 高 --labels 后端,线上"
        )
        assert intent is not None
        assert intent.action == "issue_create"
        assert intent.args.startswith("修复登录")
        assert "--desc 超时" in intent.args
        assert "--labels 后端,线上" in intent.args

    def test_inbox_open(self) -> None:
        intent = nl.parse_nl_intent("multica 收件箱 10 open")
        assert intent is not None
        assert intent.action == "inbox"
        assert "10" in intent.args
        assert "open" in intent.args

    def test_inbox_spoken(self) -> None:
        intent = nl.parse_nl_intent("看看multica收件箱未完成的")
        assert intent is not None
        assert intent.action == "inbox"
        assert "open" in intent.args

    def test_status_and_help(self) -> None:
        assert nl.parse_nl_intent("multica status").action == "status"
        assert nl.parse_nl_intent("multica 状态").action == "status"
        assert nl.parse_nl_intent("multica 帮助").action == "help"

    def test_workspace_and_project(self) -> None:
        assert nl.parse_nl_intent("multica 工作区列表").action == "workspace_list"
        assert nl.parse_nl_intent("列出multica项目").action == "project_list"

        ws = nl.parse_nl_intent("multica 切换到工作区 eason-service")
        assert ws.action == "workspace_select"
        assert ws.args == "eason-service"

        proj = nl.parse_nl_intent("multica 切换到项目 前端重构")
        assert proj.action == "project_select"
        assert proj.args == "前端重构"

        wsc = nl.parse_nl_intent("multica 新建工作区 测试环境")
        assert wsc.action == "workspace_create"
        assert "测试环境" in wsc.args

        prc = nl.parse_nl_intent("multica 创建项目 前端重构 描述 重构计划")
        assert prc.action == "project_create"
        assert "前端重构" in prc.args
        assert "--desc" in prc.args

    def test_non_control_chat_is_ignored(self) -> None:
        assert nl.parse_nl_intent("multica是什么？好用吗") is None
        assert nl.parse_nl_intent("我喜欢 multica 这个名字") is None

    def test_no_keyword_is_ignored(self) -> None:
        assert nl.parse_nl_intent("建个issue：修复登录") is None


class TestIssueFieldExtract:
    def test_priority_and_due(self) -> None:
        fields = nl._extract_issue_fields(
            "修复支付，优先级紧急，截止 2026-10-01，标签 支付,线上"
        )
        assert fields["title"] == "修复支付"
        assert fields["priority"] == "urgent"
        assert fields["due"] == "2026-10-01"
        assert "支付" in fields["labels"]

    def test_status_token(self) -> None:
        fields = nl._extract_issue_fields("登录重构 状态 进行中")
        assert "登录重构" in fields["title"]
        assert fields["status"] == "in_progress"


class TestLLMHelpers:
    def test_extract_json_object_fenced(self) -> None:
        raw = '好的\n```json\n{"action":"inbox","args":"5 open"}\n```'
        data = nl.extract_json_object(raw)
        assert data["action"] == "inbox"

    def test_extract_json_object_inline(self) -> None:
        data = nl.extract_json_object('{"action":"status","args":""}')
        assert data["action"] == "status"

    def test_intent_from_llm_payload(self) -> None:
        intent = nl.intent_from_llm_payload(
            {"action": "issue_create", "args": "修复登录 --priority 高"}
        )
        assert intent is not None
        assert intent.source == "llm"
        assert intent.action == "issue_create"

        assert nl.intent_from_llm_payload({"action": "none"}) is None
        assert nl.intent_from_llm_payload({"action": "hack"}) is None
        assert nl.intent_from_llm_payload(None) is None

    def test_extract_llm_reply_text_variants(self) -> None:
        class R1:
            completion_text = '{"action":"help"}'

        class R2:
            result_completion = '{"action":"status"}'

        assert "help" in nl.extract_llm_reply_text(R1())
        assert "status" in nl.extract_llm_reply_text(R2())
        assert nl.extract_llm_reply_text('{"action":"inbox"}') == '{"action":"inbox"}'


class TestConfigDefaults:
    def test_nl_defaults_present(self) -> None:
        defaults = config.CONFIG_DEFAULTS
        assert defaults["nl_enabled"] is True
        assert defaults["nl_keyword"] == "multica"
        assert defaults["nl_llm_enabled"] is True

    def test_merge_preserves_nl_flags(self) -> None:
        merged = config.deep_merge(
            config.CONFIG_DEFAULTS, {"nl_enabled": False, "nl_keyword": "桥接"}
        )
        assert merged["nl_enabled"] is False
        assert merged["nl_keyword"] == "桥接"
        assert merged["api_url"] == config.CONFIG_DEFAULTS["api_url"]
