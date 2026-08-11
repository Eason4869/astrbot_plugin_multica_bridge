"""Multica 桥接插件 Web API。

提供连接测试、配置保存、数据同步等 REST 接口。
"""

from __future__ import annotations

from typing import Any

from .config import (
    CONFIG_DEFAULTS,
    coerce_to_default_type,
    deep_merge,
    save_plugin_config,
)

PLUGIN_NAME = "astrbot_plugin_multica_bridge"


def _mask_token(token: str) -> str:
    """脱敏 token：保留前 4 后 4 字符。"""
    s = str(token or "")
    if len(s) <= 8:
        return s[:2] + "****" if len(s) > 2 else "****"
    return s[:4] + "****" + s[-4:]


class WebApiMixin:
    """注册 REST Web API 的 Mixin。"""

    context: Any
    config: Any
    get_data_dir: Any

    def register_routes(self) -> None:
        """注册所有 Web API 路由。"""
        try:
            reg = self.context.register_web_api
            prefix = f"/{PLUGIN_NAME}"
            routes: list[tuple[str, Any, list[str], str]] = [
                (f"{prefix}/config", self.api_config, ["GET"], "当前插件配置"),
                (
                    f"{prefix}/actions/save_config",
                    self.api_action_save_config,
                    ["POST"],
                    "保存配置（热生效）",
                ),
                (
                    f"{prefix}/actions/test_connection",
                    self.api_action_test_connection,
                    ["POST"],
                    "测试 Multica 连接",
                ),
                (
                    f"{prefix}/actions/sync",
                    self.api_action_sync,
                    ["POST"],
                    "同步数据到 Multica",
                ),
            ]
            for route, handler, methods, desc in routes:
                try:
                    reg(route, handler, methods, desc)
                except Exception:
                    pass
        except Exception:
            pass

    @staticmethod
    def _ok(data: Any = None, **extra: Any) -> dict[str, Any]:
        out: dict[str, Any] = {"success": True}
        if data is not None:
            out["data"] = data
        out.update(extra)
        return out

    @staticmethod
    def _err(message: str) -> dict[str, Any]:
        return {"success": False, "error": message}

    async def api_config(self, **kwargs: Any) -> dict[str, Any]:
        """GET /config：当前插件配置（token 脱敏）。"""
        try:
            cfg = getattr(self, "cfg", None) or {}
            out = dict(cfg) if isinstance(cfg, dict) else {}
            if out.get("token"):
                out["token"] = _mask_token(out["token"])
            return self._ok(out)
        except Exception as e:
            return self._err(str(e))

    async def api_action_save_config(self, **kwargs: Any) -> dict[str, Any]:
        """POST /actions/save_config：保存配置（校验 + 热生效）。"""
        try:
            from quart import request

            try:
                body = await request.json
            except Exception:
                body = None
            if not isinstance(body, dict):
                return self._err("请求体必须是 JSON 对象")

            cur = dict(getattr(self, "cfg", None) or {})
            for k, v in body.items():
                if k in CONFIG_DEFAULTS:
                    cur[k] = coerce_to_default_type(v, CONFIG_DEFAULTS[k])

            data_dir = getattr(self, "_data_dir", None) or str(self.get_data_dir())
            save_plugin_config(data_dir, cur)
            self.cfg = deep_merge(CONFIG_DEFAULTS, cur)

            return self._ok({"saved": list(k for k in body if k in CONFIG_DEFAULTS)})
        except Exception as e:
            return self._err(str(e))

    async def api_action_test_connection(self, **kwargs: Any) -> dict[str, Any]:
        """POST /actions/test_connection：测试 Multica 连接。"""
        try:
            from .multica_client import MulticaClient

            client = MulticaClient(getattr(self, "cfg", None))
            result = await client.test_connection()
            return self._ok(result)
        except Exception as e:
            return self._err(str(e))

    async def api_action_sync(self, **kwargs: Any) -> dict[str, Any]:
        """POST /actions/sync：同步数据到 Multica。"""
        try:
            from quart import request

            from .multica_client import MulticaClient

            try:
                body = await request.json
            except Exception:
                body = {}
            client = MulticaClient(getattr(self, "cfg", None))
            result = await client.sync_data(body if isinstance(body, dict) else {})
            return self._ok(result)
        except Exception as e:
            return self._err(str(e))
