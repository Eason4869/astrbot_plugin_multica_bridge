import asyncio
from types import SimpleNamespace

from test_work_mode import Event


def test_provider_internal_typeerror_is_not_retried(nl_plugin):
    plugin, register, _ = nl_plugin
    register("inbox")
    calls = []

    async def text_chat(prompt, system_prompt=""):
        calls.append(prompt)
        raise TypeError("internal failure")

    plugin.context.get_using_provider = lambda *a: SimpleNamespace(text_chat=text_chat)
    asyncio.run(
        plugin._llm_parse_intent(Event(), "multica 帮我整理一下任务", "multica")
    )
    assert len(calls) == 1


def test_provider_timeout_cancels_and_no_mutation_is_dispatched(nl_plugin, monkeypatch):
    from astrbot_plugin_multica_bridge import natural_language as runtime

    plugin, register, _ = nl_plugin
    register("inbox")
    monkeypatch.setattr(runtime, "NL_TIMEOUT", 0.02)
    cancelled = []

    async def text_chat(**kwargs):
        try:
            await asyncio.sleep(1)
        finally:
            cancelled.append(True)

    plugin.context.get_using_provider = lambda *a: SimpleNamespace(text_chat=text_chat)
    result = asyncio.run(
        plugin._llm_parse_intent(Event(), "multica 帮我整理一下任务", "multica")
    )
    assert result is None and cancelled


def test_model_cannot_turn_negated_or_quoted_text_into_mode_entry(nl_plugin):
    plugin, register, _ = nl_plugin
    register("enter")
    calls = []

    async def text_chat(**kwargs):
        calls.append(True)
        return '{"action":"work_enter","fields":{}}'

    plugin.context.get_using_provider = lambda *a: SimpleNamespace(text_chat=text_chat)
    result = asyncio.run(
        plugin._llm_parse_intent(Event(), "不要进入multica模式", "multica")
    )
    assert result is None and not calls
