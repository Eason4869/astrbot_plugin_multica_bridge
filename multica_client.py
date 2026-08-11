"""Multica API 客户端。

提供连接测试、报表同步等桥接功能。
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from .config import CONFIG_DEFAULTS

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _is_uuid(value: str) -> bool:
    """判断字符串是否为 UUID 格式。"""
    return bool(_UUID_RE.match(value))


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
    """Multica API 轻量客户端。

    workspace_id 如果留空，会在首次 API 调用时自动从 /api/workspace 获取。
    """

    def __init__(self, cfg: dict[str, Any] | None) -> None:
        mc = get_multica_config(cfg)
        self._enabled: bool = bool(mc.get("enabled", True))
        self._api_url: str = str(mc.get("api_url", "")).rstrip("/")
        self._token: str = str(mc.get("token", ""))
        self._workspace_id: str = str(mc.get("workspace_id", ""))
        self._project_id: str = str(mc.get("project_id", ""))
        self._workspace_name: str | None = None

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
        """测试 Multica 连接是否正常。

        成功时自动缓存 workspace_id 和 workspace_name，
        用户无需手动填写 workspace_id 配置项。
        """
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
                        # 兼容两种响应结构：顶层字段 或 { data: { ... } }
                        inner = data if isinstance(data, dict) else {}
                        if "data" in inner and isinstance(inner.get("data"), dict):
                            inner = inner["data"]
                        name = inner.get("name") or None
                        wsid = inner.get("id") or None
                        # 自动缓存（当前值非 UUID 时覆盖）
                        if wsid and not _is_uuid(self._workspace_id):
                            self._workspace_id = str(wsid)
                        if name:
                            self._workspace_name = str(name)
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

    async def _ensure_workspace_id(self) -> None:
        """如果 workspace_id 为空或不是 UUID 格式，调用 /api/workspace 自动获取。"""
        if self._workspace_id and _is_uuid(self._workspace_id):
            return
        result = await self.test_connection()
        if not result["ok"]:
            raise RuntimeError(
                f"无法自动获取 workspace_id: {result['message']}。"
                "请检查 api_url 和 token 是否正确，或手动填写 workspace_id。"
            )

    async def sync_data(self, payload: dict[str, Any]) -> dict[str, Any]:
        """同步数据到 Multica。"""
        if not self._enabled:
            return {"ok": False, "message": "桥接未启用"}
        if not self._api_url or not self._token:
            return {"ok": False, "message": "API 地址或 Token 未配置"}

        # 自动发现 workspace_id
        try:
            await self._ensure_workspace_id()
        except RuntimeError as e:
            return {"ok": False, "message": str(e)}

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
