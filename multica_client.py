"""Multica API 客户端。

提供连接测试、Issue 创建、工作区管理等桥接功能。
"""

from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import urlencode, urljoin

from .config import CONFIG_DEFAULTS

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# 指派人名称缓存：{(api_url, workspace_id): (时间戳, {id: name})}。
# 每条指令都会新建一个 MulticaClient，因此缓存必须放在模块级才有效。
_ASSIGNEE_CACHE: dict[str, tuple[float, dict[str, str]]] = {}
_ASSIGNEE_CACHE_TTL = 300.0


class ResourceNotFound(ValueError):
    pass


def resolve_unique_resource(value: str, items: list[dict], name_key: str) -> dict:
    target = value.strip().casefold()
    records = [item for item in items if isinstance(item, dict) and item.get("id")]
    for candidates in (
        [i for i in records if str(i["id"]).casefold() == target],
        [i for i in records if str(i.get(name_key) or "").casefold() == target],
        [
            i
            for i in records
            if len(target) >= 8 and str(i["id"]).casefold().startswith(target)
        ],
    ):
        if len(candidates) > 1:
            raise ValueError(
                "匹配到多个资源，请使用完整 ID："
                + "、".join(str(i["id"]) for i in candidates[:8])
            )
        if candidates:
            return candidates[0]
    raise ResourceNotFound("未找到资源，请核对名称或完整 ID")


def apply_context_update(
    current: dict, patch: dict, workspaces: list[dict], projects: list[dict]
) -> dict:
    from .config import merge_config_update

    updated = merge_config_update(current, patch)
    if (
        updated.get("workspace_id") != current.get("workspace_id")
        and "project_id" not in patch
    ):
        updated["project_id"] = ""
    workspace = str(updated.get("workspace_id") or "")
    if workspace:
        workspace = str(resolve_unique_resource(workspace, workspaces, "slug")["id"])
        updated["workspace_id"] = workspace
    project = str(updated.get("project_id") or "")
    if project:
        if not workspace:
            if len(workspaces) != 1 or not workspaces[0].get("id"):
                raise ValueError("请选择明确的工作区后再选择项目")
            workspace = str(workspaces[0]["id"])
            updated["workspace_id"] = workspace
        selected = resolve_unique_resource(project, projects, "title")
        if selected.get("workspace_id") and str(selected["workspace_id"]) != workspace:
            raise ValueError("项目不属于选定工作区")
        updated["project_id"] = str(selected["id"])
    return updated


def _is_uuid(value: str) -> bool:
    """判断字符串是否为 UUID 格式。"""
    return bool(_UUID_RE.match(value))


def mask_secret(secret: str, keep: int = 4) -> str:
    """脱敏敏感字符串：保留首尾各 ``keep`` 个字符。"""
    s = str(secret or "")
    if not s:
        return "（未配置）"
    if len(s) <= keep * 2:
        return s[:2] + "****" if len(s) > 2 else "****"
    return s[:keep] + "****" + s[-keep:]


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


PERMISSION_DENIED = "您没有使用Multica的权限，请联系管理员获取使用资格"


def event_access_origins(event) -> list[str]:
    origins = [str(event.unified_msg_origin or "")]
    group = str(event.get_group_id() or "")
    if group:
        origins.append(f"{event.get_platform_id()}:GroupMessage:{group}")
    return list(dict.fromkeys(origins))


def check_chat_allowed(
    cfg: dict[str, Any] | None, chat_type: str, chat_id: str, umo: str = ""
) -> bool:
    """Legacy signature; authorization now always uses the sender user ID."""
    if not isinstance(cfg, dict) or not str(chat_id).strip():
        return False
    allowed = cfg.get("multica_whitelist", [])
    if not isinstance(allowed, (list, tuple)):
        return False
    entries = {str(i).strip() for i in allowed if str(i).strip()}
    return str(chat_id).strip() in entries or bool(umo and umo in entries)


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

        成功时自动缓存 workspace_name，用户无需手动填写 workspace_id 配置项；
        同时返回当前工作区的 id/slug，便于 /multica status 展示。
        """
        result = await self.list_workspaces()
        if not result["ok"]:
            return {
                "ok": False,
                "message": result["message"],
                "workspace_name": None,
                "workspace_id": None,
                "workspace_slug": None,
            }
        try:
            ws, name, wsid = self._pick_workspace(result["workspaces"])
        except ValueError as exc:
            return {
                "ok": False,
                "message": str(exc),
                "workspace_name": None,
                "workspace_id": None,
                "workspace_slug": None,
            }
        if name:
            self._workspace_name = str(name)
        return {
            "ok": True,
            "message": "连接成功",
            "workspace_name": name,
            "workspace_id": wsid,
            "workspace_slug": (ws or {}).get("slug"),
        }

    async def get_project_title(self, project_id: str) -> str:
        """best-effort：按 id 解析项目标题（失败返回空串）。"""
        if not project_id:
            return ""
        result = await self.list_projects()
        if not result.get("ok"):
            return ""
        proj = self.find_project(project_id, result.get("projects") or [])
        return str((proj or {}).get("title") or "")

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
            async with aiohttp.ClientSession(trust_env=False) as session:
                async with session.get(
                    url,
                    headers=self._headers(),
                    allow_redirects=False,
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
                    return {
                        "ok": False,
                        "message": f"Multica HTTP {resp.status}",
                        "workspaces": [],
                    }
        except Exception as e:
            return {
                "ok": False,
                "message": f"连接失败：{type(e).__name__}",
                "workspaces": [],
            }

    def _pick_workspace(
        self, workspaces: list[dict[str, Any]]
    ) -> tuple[dict[str, Any] | None, str | None, str | None]:
        """从工作区列表中挑出当前工作区。

        显式配置必须匹配；留空且只有一个工作区时才自动选择。
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
        if want:
            raise ValueError("指定工作区不存在或不可访问，请在设置中重新选择")
        choices = [w for w in workspaces if isinstance(w, dict) and w.get("id")]
        if len(choices) != 1:
            raise ValueError(
                "请选择工作区：存在多个工作区" if choices else "没有可访问的工作区"
            )
        ws = choices[0]
        return ws, ws.get("name") or None, ws.get("id") or None

    def find_workspace(
        self, value: str, workspaces: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """按 id（支持完整 UUID 或前缀）或 slug（不区分大小写）查找工作区。"""
        if not value.strip():
            return None
        candidates = [
            dict(item, slug=item.get("slug") or item.get("name") or "")
            for item in workspaces
            if isinstance(item, dict)
        ]
        try:
            return resolve_unique_resource(value, candidates, "slug")
        except ResourceNotFound:
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
        try:
            _ws, _name, wsid = self._pick_workspace(result["workspaces"])
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc
        if wsid:
            self._workspace_id = str(wsid)

    async def validate_project(self, project_id: str) -> str:
        """Resolve a project within this client's effective workspace before writes."""
        if not project_id:
            return ""
        await self._ensure_workspace_id()
        result = await self.list_projects()
        if not result.get("ok"):
            raise ValueError("无法验证项目，请检查连接和工作区配置")
        try:
            project = resolve_unique_resource(
                project_id, result.get("projects") or [], "title"
            )
        except ValueError as exc:
            raise ValueError("项目不存在或不唯一，请重新选择项目") from exc
        if (
            project.get("workspace_id")
            and str(project["workspace_id"]) != self._workspace_id
        ):
            raise ValueError("项目不属于当前工作区，请重新选择项目")
        return str(project["id"])

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

        try:
            effective_project = await self.validate_project(
                project_id or self._project_id
            )
        except (ValueError, RuntimeError) as exc:
            return {"ok": False, "message": str(exc)}

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
        if effective_project:
            payload["project_id"] = effective_project
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
            async with aiohttp.ClientSession(trust_env=False) as session:
                async with session.post(
                    url,
                    headers=self._headers(),
                    allow_redirects=False,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status in (200, 201):
                        data = await resp.json()
                        ident = (
                            data.get("identifier") or data.get("id") or "（未返回编号）"
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
                    return {
                        "ok": False,
                        "message": f"Multica HTTP {resp.status}",
                    }
        except Exception as e:
            return {
                "ok": False,
                "message": f"创建失败：{type(e).__name__}",
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
            async with aiohttp.ClientSession(trust_env=False) as session:
                async with session.post(
                    url,
                    headers=self._headers(),
                    allow_redirects=False,
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
                    return {
                        "ok": False,
                        "message": f"Multica HTTP {resp.status}",
                    }
        except Exception as e:
            return {
                "ok": False,
                "message": f"创建工作区失败：{type(e).__name__}",
            }

    async def list_projects(self) -> dict[str, Any]:
        """列出当前工作区下的所有项目。

        直接调用 ``GET /api/projects``，query 参数传 workspace_id（与 create_issue 一致）。
        返回 ``{"ok": True, "projects": [{id, title, ...}, ...]}``
        或 ``{"ok": False, "message": "..."}``。
        """
        if not self._enabled:
            return {"ok": False, "message": "Multica 桥接未启用", "projects": []}
        if not self._api_url or not self._token:
            return {
                "ok": False,
                "message": "Multica API 地址或 Token 未配置",
                "projects": [],
            }

        try:
            await self._ensure_workspace_id()
        except RuntimeError as e:
            return {"ok": False, "message": str(e), "projects": []}
        if not self._workspace_id:
            return {
                "ok": False,
                "message": "无法确定工作区：请检查 api_url/token，或手动填写 workspace_id",
                "projects": [],
            }

        import aiohttp

        try:
            url = urljoin(
                self._api_url + "/",
                "api/projects?" + urlencode({"workspace_id": self._workspace_id}),
            )
            async with aiohttp.ClientSession(trust_env=False) as session:
                async with session.get(
                    url,
                    headers=self._headers(),
                    allow_redirects=False,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if isinstance(data, dict):
                            projects = data.get("projects") or []
                        elif isinstance(data, list):
                            projects = data
                        else:
                            projects = []
                        return {"ok": True, "projects": list(projects)}
                    if resp.status == 401:
                        return {
                            "ok": False,
                            "message": "Token 无效，请在 Multica 控制台重新生成",
                            "projects": [],
                        }
                    return {
                        "ok": False,
                        "message": f"Multica HTTP {resp.status}",
                        "projects": [],
                    }
        except Exception as e:
            return {
                "ok": False,
                "message": f"获取项目列表失败：{type(e).__name__}",
                "projects": [],
            }

    def find_project(
        self, value: str, projects: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """按 id（支持完整 UUID 或前缀）查找项目。"""
        if not value.strip():
            return None
        try:
            return resolve_unique_resource(value, projects, "title")
        except ResourceNotFound:
            return None

    async def create_project(
        self,
        *,
        title: str,
        description: str = "",
        icon: str = "",
        status: str = "",
        lead: str = "",
    ) -> dict[str, Any]:
        """通过 Multica HTTP API 创建项目。

        ``POST /api/projects``，query 参数传 workspace_id（与 create_issue 一致），
        请求体字段与 CLI 对齐：title 必填，description/icon/status/lead 可选。
        """
        if not self._enabled:
            return {"ok": False, "message": "Multica 桥接未启用"}
        if not self._api_url or not self._token:
            return {"ok": False, "message": "API 地址或 Token 未配置"}
        if not title or not title.strip():
            return {"ok": False, "message": "缺少项目标题"}

        try:
            await self._ensure_workspace_id()
        except RuntimeError as e:
            return {"ok": False, "message": str(e)}
        if not self._workspace_id:
            return {
                "ok": False,
                "message": "无法确定工作区：请检查 api_url/token，或手动填写 workspace_id",
            }

        payload: dict[str, Any] = {"title": title.strip()}
        if description:
            payload["description"] = description
        if icon:
            payload["icon"] = icon
        if status:
            payload["status"] = status
        if lead:
            payload["lead"] = lead

        import aiohttp

        try:
            url = urljoin(
                self._api_url + "/",
                "api/projects?" + urlencode({"workspace_id": self._workspace_id}),
            )
            async with aiohttp.ClientSession(trust_env=False) as session:
                async with session.post(
                    url,
                    headers=self._headers(),
                    allow_redirects=False,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status in (200, 201):
                        data = await resp.json()
                        ptitle = data.get("title") or title
                        pid = data.get("id") or "（未返回 id）"
                        return {
                            "ok": True,
                            "message": f"已创建项目 {ptitle}（{pid}）",
                            "project": data,
                        }
                    if resp.status == 401:
                        return {
                            "ok": False,
                            "message": "Token 无效，请在 Multica 控制台重新生成",
                        }
                    return {
                        "ok": False,
                        "message": f"Multica HTTP {resp.status}",
                    }
        except Exception as e:
            return {
                "ok": False,
                "message": f"创建项目失败：{type(e).__name__}",
            }

    async def list_issues(
        self,
        *,
        limit: int = 50,
        status: str = "",
        sort: str = "created_at",
        direction: str = "desc",
    ) -> dict[str, Any]:
        """列出当前工作区 Issue。

        直接调用 ``GET /api/issues``，query 参数传 workspace_id（与 create_issue 一致）。
        API 不支持按 updated_at 排序，因此这里仅以 created_at 倒序获取一个较新的窗口，
        最终排序由调用方（inbox 命令）在本地按 updated_at 完成。
        """
        if not self._enabled:
            return {"ok": False, "message": "Multica 桥接未启用"}
        if not self._api_url or not self._token:
            return {"ok": False, "message": "API 地址或 Token 未配置"}

        try:
            await self._ensure_workspace_id()
        except RuntimeError as e:
            return {"ok": False, "message": str(e)}
        if not self._workspace_id:
            return {
                "ok": False,
                "message": "无法确定工作区：请检查 api_url/token，或手动填写 workspace_id",
            }

        params: dict[str, Any] = {
            "workspace_id": self._workspace_id,
            "limit": max(1, int(limit)),
        }
        if status:
            params["status"] = status
        if sort:
            params["sort"] = sort
            if direction:
                params["direction"] = direction

        import aiohttp

        try:
            url = urljoin(
                self._api_url + "/",
                "api/issues?" + urlencode(params),
            )
            async with aiohttp.ClientSession(trust_env=False) as session:
                async with session.get(
                    url,
                    headers=self._headers(),
                    allow_redirects=False,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if isinstance(data, dict):
                            issues = data.get("issues") or []
                        elif isinstance(data, list):
                            issues = data
                        else:
                            issues = []
                        return {"ok": True, "issues": list(issues)}
                    if resp.status == 401:
                        return {
                            "ok": False,
                            "message": "Token 无效，请在 Multica 控制台重新生成",
                        }
                    return {
                        "ok": False,
                        "message": f"Multica HTTP {resp.status}",
                    }
        except Exception as e:
            return {
                "ok": False,
                "message": f"获取收件箱失败：{type(e).__name__}",
            }

    async def _fetch_id_name_map(self, path: str, id_key: str = "id") -> dict[str, str]:
        """best-effort：GET 一个返回 [{id, name}, ...] 的端点，映射 id -> name。

        任何失败（网络、404、解析异常）都返回空 dict，不抛异常。
        """
        try:
            import aiohttp

            url = urljoin(self._api_url + "/", path)
            async with aiohttp.ClientSession(trust_env=False) as session:
                async with session.get(
                    url,
                    headers=self._headers(),
                    allow_redirects=False,
                    timeout=aiohttp.ClientTimeout(total=8),
                ) as resp:
                    if resp.status != 200:
                        return {}
                    data = await resp.json()
                    if not isinstance(data, list):
                        return {}
                    out: dict[str, str] = {}
                    for item in data:
                        if not isinstance(item, dict):
                            continue
                        kid = item.get(id_key)
                        name = item.get("name")
                        if kid and name:
                            out[str(kid)] = str(name)
                    return out
        except Exception:
            return {}

    async def resolve_assignee_names(
        self,
        only_ids: set[str] | None = None,
    ) -> dict[str, str]:
        """best-effort：把 assignee_id 解析为可读名称（智能体/团队/成员）。

        分别请求 agents/squads/members 列表并合并为 id -> name 映射；
        任何端点失败都会自动降级，不影响 inbox 主流程。
        结果按 ``(api_url, workspace_id)`` 缓存 ``_ASSIGNEE_CACHE_TTL`` 秒，
        避免每次收件箱查询都发起 3 个额外请求。

        Args:
            only_ids: 只返回这些 id 的映射（为 None 时返回全部）。
        """
        if not self._workspace_id:
            return {}

        import hashlib

        cache_key = f"{self._api_url}|{self._workspace_id}|{hashlib.sha256(self._token.encode()).hexdigest()}"
        now = time.monotonic()
        cached = _ASSIGNEE_CACHE.get(cache_key)
        if cached and now - cached[0] < _ASSIGNEE_CACHE_TTL:
            merged = cached[1]
        else:
            merged = await self._fetch_all_assignees()
            _ASSIGNEE_CACHE[cache_key] = (now, merged)

        if only_ids:
            return {k: v for k, v in merged.items() if k in only_ids}
        return dict(merged)

    async def _fetch_all_assignees(self) -> dict[str, str]:
        """并发拉取 agents/squads/members 并合并为 id -> name（失败降级为空）。"""
        try:
            import asyncio

            qs = urlencode({"workspace_id": self._workspace_id})

            async def _fetch_members() -> dict[str, str]:
                # 成员端点路径存在两种可能，依次尝试
                for path in (
                    f"api/members?{qs}",
                    f"api/workspaces/{self._workspace_id}/members",
                ):
                    m = await self._fetch_id_name_map(path, id_key="user_id")
                    if m:
                        return m
                return {}

            results = await asyncio.gather(
                self._fetch_id_name_map(f"api/agents?{qs}"),
                self._fetch_id_name_map(f"api/squads?{qs}"),
                _fetch_members(),
                return_exceptions=True,
            )
            merged: dict[str, str] = {}
            for r in results:
                if isinstance(r, dict):
                    merged.update(r)
            return merged
        except Exception:
            return {}
