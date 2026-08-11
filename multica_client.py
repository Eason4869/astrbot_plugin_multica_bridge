"""Multica API 客户端。

提供连接测试、报表同步等桥接功能。
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from .config import CONFIG_DEFAULTS


def get_multica_config(cfg: dict[str, Any] | None) -> dict[str, Any]:
    """从插件配置中提取 Multica 相关配置。"""
    defaults = dict(CONFIG_DEFAULTS)
    if not isinstance(cfg, dict):
        return defaults
    out = dict(defaults)
    for k in defaults:
        if k in cfg:
            out[k] = cfg[k]
    return out


def check_chat_allowed(cfg: dict[str, Any] | None, chat_type: str, chat_id: str) -> bool:
    """检查指定会话是否在黑/白名单配置中允许执行。

    chat_type: "group" 或 "private"
    chat_id: 群号或用户 QQ 号（字符串）
    返回 True 表示允许，False 表示应跳过。
    """
    if not isinstance(cfg, dict):
        return True
    mode_key = f"{chat_type}_chat_mode"
    list_key = f"{chat_type}_chat_list"
    mode = str(cfg.get(mode_key, "disabled"))
    id_list = cfg.get(list_key, [])
    if not isinstance(id_list, (list, tuple)):
        id_list = []
    # 转换为字符串列表
    id_set = {str(i).strip() for i in id_list if str(i).strip()}
    chat_str = str(chat_id).strip()
    if mode == "blacklist":
        return chat_str not in id_set
    if mode == "whitelist":
        return chat_str in id_set
    # disabled: 不限制
    return True


class MulticaClient:
    """Multica API 轻量客户端。"""

    def __init__(self, cfg: dict[str, Any] | None) -> None:
        mc = get_multica_config(cfg)
        self._enabled: bool = bool(mc.get("enabled", True))
        self._api_url: str = str(mc.get("api_url", "")).rstrip("/")
        self._token: str = str(mc.get("token", ""))
        self._workspace_id: str = str(mc.get("workspace_id", ""))
        self._project_id: str = str(mc.get("project_id", ""))

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def test_connection(self) -> dict[str, Any]:
        """测试 Multica 连接是否正常。"""
        if not self._enabled:
            return {"ok": False, "message": "Multica 桥接未启用", "workspace_name": None}
        if not self._api_url or not self._token:
            return {
                "ok": False,
                "message": "Multica API 地址或 Token 未配置",
                "workspace_name": None,
            }

        import aiohttp

        try:
            url = urljoin(self._api_url + "/", "api/workspace")
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=self._headers(),
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        name = (
                            data.get("name")
                            or (data.get("data", {}) or {}).get("name")
                            or None
                        )
                        return {"ok": True, "message": "连接成功", "workspace_name": name}
                    body = await resp.text()
                    return {
                        "ok": False,
                        "message": f"HTTP {resp.status}: {body[:200]}",
                        "workspace_name": None,
                    }
        except Exception as e:
            return {
                "ok": False,
                "message": f"连接失败：{type(e).__name__}: {e}",
                "workspace_name": None,
            }

    async def sync_data(self, payload: dict[str, Any]) -> dict[str, Any]:
        """同步数据到 Multica。"""
        if not self._enabled:
            return {"ok": False, "message": "桥接未启用"}
        if not self._api_url or not self._token:
            return {"ok": False, "message": "API 地址或 Token 未配置"}

        import aiohttp

        payload["workspace_id"] = self._workspace_id
        payload["project_id"] = self._project_id

        try:
            url = urljoin(self._api_url + "/", "api/data/sync")
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=self._headers(),
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status in (200, 201, 204):
                        return {"ok": True, "message": "同步成功"}
                    body = await resp.text()
                    return {"ok": False, "message": f"HTTP {resp.status}: {body[:200]}"}
        except Exception as e:
            return {"ok": False, "message": f"同步失败：{type(e).__name__}: {e}"}
