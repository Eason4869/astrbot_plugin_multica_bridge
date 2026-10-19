import ast
import asyncio
import importlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from astrbot_plugin_multica_bridge.session_store import SessionStore
from test_commands import _install_astrbot_stubs

ROOT = Path(__file__).resolve().parents[1]


def test_shipped_python_uses_only_official_logger_imports():
    spec = importlib.util.spec_from_file_location(
        "package_logger_policy", ROOT / "scripts/build_package.py"
    )
    package = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(package)
    violations = []
    for name in package.FILES:
        if not name.endswith(".py"):
            continue
        tree = ast.parse((ROOT / name).read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for item in node.names:
                    if item.name.split(".")[0] == "logging":
                        violations.append(f"{name}:{node.lineno} stdlib logging")
            if isinstance(node, ast.ImportFrom):
                if (node.module or "").split(".")[0] == "logging":
                    violations.append(f"{name}:{node.lineno} stdlib logging")
                if any(item.name == "logger" for item in node.names):
                    if node.module != "astrbot.api":
                        violations.append(f"{name}:{node.lineno} unofficial logger")
    assert not violations, "\n".join(violations)


@pytest.mark.parametrize("name", ["main", "work_mode", "reply_worker", "web_api"])
def test_logging_modules_expose_public_api_logger(name):
    _install_astrbot_stubs()
    module = importlib.import_module("astrbot_plugin_multica_bridge." + name)
    assert hasattr(module, "logger"), f"{name} must import astrbot.api.logger"
    assert module.logger is importlib.import_module("astrbot.api").logger


def test_main_and_work_mode_use_imported_api_logger(tmp_path):
    _install_astrbot_stubs()
    main = importlib.import_module("astrbot_plugin_multica_bridge.main")
    mode = importlib.import_module("astrbot_plugin_multica_bridge.work_mode")
    plugin = main.Main(SimpleNamespace())
    assert plugin.log is main.logger
    service = mode.WorkMode(plugin, SessionStore(str(tmp_path)), None, None)
    assert service.log is mode.logger


def test_worker_failure_uses_official_logger_without_exception_body(
    tmp_path, monkeypatch
):
    _install_astrbot_stubs()
    module = importlib.import_module("astrbot_plugin_multica_bridge.reply_worker")
    api_logger = Mock()
    monkeypatch.setattr(module, "logger", api_logger, raising=False)

    async def run():
        store = SessionStore(str(tmp_path))
        store.update("room", active=True, generation=1, session_id="chat", origin="qq")

        async def messages(*args):
            raise RuntimeError("PRIVATE TOKEN MUST NOT LEAK")

        async def push(*args):
            store.update("room", active=False)

        async def no_delay(*args):
            pass

        monkeypatch.setattr(module.asyncio, "sleep", no_delay)
        await module.ReplyWorker(store, push)._run(
            "room", 1, SimpleNamespace(messages=messages)
        )

    asyncio.run(run())
    api_logger.warning.assert_called_once()
    logged = str(api_logger.warning.call_args)
    assert "RuntimeError" in logged
    assert "PRIVATE TOKEN" not in logged
