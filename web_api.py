"""Multica 桥接插件 Web API。

提供连接测试、配置保存等 REST 接口，供插件 Pages（WebUI 设置页）调用。

路由前缀使用插件目录名动态生成，避免重命名插件目录后全部 404；
请求体读取优先使用 AstrBot 官方的 ``astrbot.api.web.request``（新版），
不可用时回退到 Quart 的 ``request``（旧版兼容）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from astrbot import logger
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

from .config import (
    CONFIG_DEFAULTS,
    coerce_to_default_type,
    deep_merge,
    save_plugin_config,
)
from .multica_client import mask_secret

# 插件目录名即 Dashboard 用于路由的插件标识；改名后自动跟随
PLUGIN_NAME = Path(__file__).resolve().parent.name or "astrbot_plugin_multica_bridge"

try:  # AstrBot 新版插件 Web API 请求代理
    from astrbot.api.web import request as _plugin_request
except Exception:  # pragma: no cover - 兼容旧版本
    _plugin_request = None


async def _read_json_body() -> Any:
    """读取请求 JSON 体；解析失败返回 None。"""
    if _plugin_request is not None:
        try:
            return await _plugin_request.json(default=None)
        except Exception:
            return None
    try:  # 旧版 AstrBot：Quart 兼容层
        from quart import request as quart_request

        return await quart_request.json
    except Exception:
        return None


class WebApiMixin:
    """注册 REST Web API 的 Mixin。"""

    context: Any
    config: Any
    name: str

    def register_routes(self) -> None:
        """注册所有 Web API 路由。"""
        try:
            reg = self.context.register_web_api
        except Exception as e:
            logger.error("[multica_bridge] 无法获取 register_web_api，Web API 未注册: %s", e)
            return

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
        ]
        for route, handler, methods, desc in routes:
            try:
                reg(route, handler, methods, desc)
            except Exception as e:
                logger.error("[multica_bridge] 注册路由 %s 失败: %s", route, e)

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
                out["token"] = mask_secret(out["token"])
            return self._ok(out)
        except Exception as e:
            logger.error("[multica_bridge] 读取配置失败: %s", e)
            return self._err(str(e))

    async def api_action_save_config(self, **kwargs: Any) -> dict[str, Any]:
        """POST /actions/save_config：保存配置（校验 + 热生效）。

        只处理请求体中出现的键（增量更新），避免前端整份回写覆盖
        聊天指令刚切换过的 workspace_id / project_id。
        """
        try:
            body = await _read_json_body()
            if not isinstance(body, dict):
                return self._err("请求体必须是 JSON 对象")

            cur = dict(getattr(self, "cfg", None) or {})
            saved: list[str] = []
            for k, v in body.items():
                if k not in CONFIG_DEFAULTS:
                    continue
                # 跳过脱敏 token：前端加载配置时 token 已脱敏（如 tok****ken），
                # 若保存时传来的 token 含掩码标记，说明用户未修改，保留原值
                if k == "token" and isinstance(v, str) and "****" in v:
                    continue
                cur[k] = coerce_to_default_type(v, CONFIG_DEFAULTS[k])
                saved.append(k)

            data_dir = getattr(self, "_data_dir", None) or str(
                Path(get_astrbot_data_path())
                / "plugin_data"
                / getattr(self, "name", PLUGIN_NAME)
            )
            save_plugin_config(data_dir, cur)
            self.cfg = deep_merge(CONFIG_DEFAULTS, cur)

            return self._ok({"saved": saved})
        except Exception as e:
            logger.error("[multica_bridge] 保存配置失败: %s", e)
            return self._err(str(e))

    async def api_action_test_connection(self, **kwargs: Any) -> dict[str, Any]:
        """POST /actions/test_connection：测试 Multica 连接。"""
        try:
            from .multica_client import MulticaClient

            client = MulticaClient(getattr(self, "cfg", None))
            result = await client.test_connection()
            return self._ok(result)
        except Exception as e:
            logger.error("[multica_bridge] 连接测试失败: %s", e)
            return self._err(str(e))
