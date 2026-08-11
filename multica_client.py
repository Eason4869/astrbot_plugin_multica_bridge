"""Multica API 客户端。

提供连接测试、Issue 创建、工作区管理等桥接功能。
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlencode, urljoin

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

    workspace_id 如果留空，会在首次 API 调用时自动从 /api/workspaces 获取。
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

        成功时自动缓存 workspace_name，用户无需手动填写 workspace_id 配置项。
        """
        result = await self.list_workspaces()
        if not result["ok"]:
            return {
                "ok": False,
                "message": result["message"],
                "workspace_name": None,
            }
        _ws, name, _wsid = self._pick_workspace(result["workspaces"])
        if name:
            self._workspace_name = str(name)
        return {"ok": True, "message": "连接成功", "workspace_name": name}

    async def list_workspaces(self) -> dict[str, Any]:
        """获取当前 Token 可访问的所有工作区。

        返回 ``{"ok": True, "workspaces": [{id, name, slug, ...}, ...]}``
        或 ``{"ok": False, "message": "..."}``。
        """
        if not self._enabled:
            return {"ok": False, "message": "Multica 桥接未启用", "workspaces": []}
        if not self._api_url or not self._token:
            return {
                "ok": False,
                "message": "Multica API 地址或 Token 未配置",
                "workspaces": [],
            }

        import aiohttp

        try:
            url = urljoin(self._api_url + "/", "api/workspaces")
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=self._headers(),
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # API 返回工作区列表: [{id, name, slug, ...}, ...]
                        workspaces = data if isinstance(data, list) else [data]
                        if not workspaces:
                            return {
                                "ok": False,
                                "message": "该 Token 下没有可访问的工作区",
                                "workspaces": [],
                            }
                        return {"ok": True, "workspaces": workspaces}
                    if resp.status == 401:
                        return {
                            "ok": False,
                            "message": "Token 无效，请在 Multica 控制台重新生成",
                            "workspaces": [],
                        }
                    body = await resp.text()
                    return {
                        "ok": False,
                        "message": f"HTTP {resp.status}: {body[:200]}",
                        "workspaces": [],
                    }
        except Exception as e:
            return {
                "ok": False,
                "message": f"连接失败：{type(e).__name__}: {e}",
                "workspaces": [],
            }

    def _pick_workspace(
        self, workspaces: list[dict[str, Any]]
    ) -> tuple[dict[str, Any] | None, str | None, str | None]:
        """从工作区列表中挑出当前工作区。

        优先匹配配置的 workspace_id（支持 UUID 或 slug），
        未配置或未命中时取第一个，与旧版自动获取行为一致。
        返回 (workspace, name, id)。
        """
        want = (self._workspace_id or "").strip().lower()
        for ws in workspaces:
            if not isinstance(ws, dict):
                continue
            wsid = str(ws.get("id") or "").strip().lower()
            slug = str(ws.get("slug") or "").strip().lower()
            if want and want in (wsid, slug):
                return ws, ws.get("name") or None, ws.get("id") or None
        ws = next((w for w in workspaces if isinstance(w, dict)), None)
        if ws is None:
            return None, None, None
        return ws, ws.get("name") or None, ws.get("id") or None

    def find_workspace(self, value: str, workspaces: list[dict[str, Any]]) -> dict[str, Any] | None:
        """按 id（支持完整 UUID 或前缀）或 slug（不区分大小写）查找工作区。"""
        target = (value or "").strip().lower()
        if not target:
            return None
        for ws in workspaces:
            if not isinstance(ws, dict):
                continue
            wsid = str(ws.get("id") or "").strip().lower()
            slug = str(ws.get("slug") or "").strip().lower()
            if target in (wsid, slug) or (len(target) >= 8 and wsid.startswith(target)):
                return ws
        return None

    async def _ensure_workspace_id(self) -> None:
        """如果 workspace_id 为空或不是 UUID 格式，调用 /api/workspaces 自动获取。"""
        if self._workspace_id and _is_uuid(self._workspace_id):
            return
        result = await self.list_workspaces()
        if not result["ok"]:
            raise RuntimeError(
                f"无法自动获取 workspace_id: {result['message']}。"
                "请检查 api_url 和 token 是否正确，或手动填写 workspace_id。"
            )
        _ws, _name, wsid = self._pick_workspace(result["workspaces"])
        if wsid:
            self._workspace_id = str(wsid)

    async def create_issue(
        self,
        *,
        title: str,
        description: str = "",
        priority: str = "",
        status: str = "",
        assignee_id: str = "",
        project_id: str = "",
        parent_id: str = "",
        due_date: str = "",
        labels: list[str] | None = None,
    ) -> dict[str, Any]:
        """通过 Multica HTTP API 创建 Issue。

        直接调用 ``POST /api/issues``，不依赖本机是否安装 ``multica`` CLI。
        也不依赖 CLI 是否加入 PATH —— 规避“本机未安装 multica”这类误报。
        """
        if not self._enabled:
            return {"ok": False, "message": "Multica 桥接未启用"}
        if not self._api_url or not self._token:
            return {"ok": False, "message": "API 地址或 Token 未配置"}
        if not title or not title.strip():
            return {"ok": False, "message": "缺少 Issue 标题"}

        # 自动发现 workspace_id
        try:
            await self._ensure_workspace_id()
        except RuntimeError as e:
            return {"ok": False, "message": str(e)}
        if not self._workspace_id:
            return {
                "ok": False,
                "message": "无法确定工作区：请检查 api_url/token，或手动填写 workspace_id",
            }

        payload: dict[str, Any] = {
            "title": title.strip(),
        }
        if description:
            payload["description"] = description
        if priority:
            payload["priority"] = priority
        if status:
            payload["status"] = status
        if assignee_id:
            payload["assignee_id"] = assignee_id
        if project_id:
            payload["project_id"] = project_id
        elif self._project_id:
            payload["project_id"] = self._project_id
        if parent_id:
            payload["parent_issue_id"] = parent_id
        if due_date:
            payload["due_date"] = due_date
        if labels:
            payload["labels"] = list(labels)

        import aiohttp

        try:
            # 注意：Multica API 通过 query 参数识别工作区，
            # body 中的 workspace_id 会被忽略（实测返回 400 提示缺失）
            url = urljoin(
                self._api_url + "/",
                "api/issues?" + urlencode({"workspace_id": self._workspace_id}),
            )
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=self._headers(),
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status in (200, 201):
                        data = await resp.json()
                        ident = (
                            data.get("identifier")
                            or data.get("id")
                            or "（未返回编号）"
                        )
                        return {
                            "ok": True,
                            "message": f"已创建 Issue {ident}",
                            "issue": data,
                        }
                    if resp.status == 401:
                        return {
                            "ok": False,
                            "message": "Token 无效，请在 Multica 控制台重新生成",
                        }
                    body = await resp.text()
                    return {
                        "ok": False,
                        "message": f"HTTP {resp.status}: {body[:300]}",
                    }
        except Exception as e:
            return {
                "ok": False,
                "message": f"创建失败：{type(e).__name__}: {e}",
            }

    async def create_workspace(
        self,
        *,
        name: str,
        slug: str = "",
        description: str = "",
        context: str = "",
        issue_prefix: str = "",
    ) -> dict[str, Any]:
        """通过 Multica HTTP API 创建工作区。

        ``POST /api/workspaces``，请求体字段与 CLI 对齐：
        name/slug 必填，description/context/issue_prefix 可选。
        """
        if not self._enabled:
            return {"ok": False, "message": "Multica 桥接未启用"}
        if not self._api_url or not self._token:
            return {"ok": False, "message": "API 地址或 Token 未配置"}
        if not name or not name.strip():
            return {"ok": False, "message": "缺少工作区名称"}
        if not slug or not slug.strip():
            return {"ok": False, "message": "缺少工作区 slug"}

        payload: dict[str, Any] = {
            "name": name.strip(),
            "slug": slug.strip().lower(),
        }
        if description:
            payload["description"] = description
        if context:
            payload["context"] = context
        if issue_prefix:
            payload["issue_prefix"] = issue_prefix

        import aiohttp

        try:
            url = urljoin(self._api_url + "/", "api/workspaces")
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=self._headers(),
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status in (200, 201):
                        data = await resp.json()
                        wslug = data.get("slug") or ""
                        return {
                            "ok": True,
                            "message": f"已创建工作区 {data.get('name') or name}（slug: {wslug}）",
                            "workspace": data,
                        }
                    if resp.status == 401:
                        return {
                            "ok": False,
                            "message": "Token 无效，请在 Multica 控制台重新生成",
                        }
                    body = await resp.text()
                    return {
                        "ok": False,
                        "message": f"HTTP {resp.status}: {body[:300]}",
                    }
        except Exception as e:
            return {
                "ok": False,
                "message": f"创建工作区失败：{type(e).__name__}: {e}",
            }
