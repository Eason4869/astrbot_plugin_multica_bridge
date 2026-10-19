"""Multica 桥接插件配置。

配置结构：CONFIG_DEFAULTS 定义所有配置项及其默认值。
插件不提供 _conf_schema.json（即 AstrBot 插件管理页面中的「齿轮」配置入口），
所有配置统一通过插件自有 config.json 管理，由 WebUI 设置页 / REST API 读写。
原因：AstrBot 通过 _conf_schema.json 生成的配置存储在 AstrBot 独立存储中，
插件运行时从未读取该配置，会导致齿轮入口的修改不生效；两套配置来源也无法可靠同步。
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from typing import Any

CONFIG_DEFAULTS: dict[str, Any] = {
    "enabled": True,
    "api_url": "https://multica.ai",
    "token": "",
    "workspace_id": "",  # 可选，留空则自动从 /api/workspaces 获取
    "project_id": "",  # 可选
    # 消息过滤配置
    "group_chat_mode": "blacklist",  # "blacklist" | "whitelist" | "disabled"
    "group_chat_list": [],  # 群号列表
    "private_chat_mode": "blacklist",  # "blacklist" | "whitelist" | "disabled"
    "private_chat_list": [],  # QQ 号列表
    # 自然语言控制：消息中含关键词（默认 multica）时自动识别意图
    "nl_enabled": True,
    "nl_keyword": "multica",
    "nl_llm_enabled": True,  # 规则解析失败时可选交给 LLM
    "work_mode_enabled": True,
    "default_agent_id": "",
}


def deep_merge(base: dict, *overrides: Any) -> dict:
    """递归合并多个 dict（后者覆盖前者）。"""
    merged = dict(base)
    for ov in overrides:
        if not isinstance(ov, dict):
            continue
        for k, v in ov.items():
            if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
                merged[k] = deep_merge(merged[k], v)
            else:
                merged[k] = v
    return merged


def load_plugin_config(data_dir: str) -> dict[str, Any]:
    """读取插件自有配置文件 config.json。"""
    path = os.path.join(data_dir, "config.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("config.json 必须是 JSON 对象；原文件未修改")
    return data


def save_plugin_config(data_dir: str, cfg: dict[str, Any]) -> None:
    """原子写插件自有配置文件。"""
    path = os.path.join(data_dir, "config.json")
    os.makedirs(data_dir, exist_ok=True)
    # Validate before backup/write. Never replace an unreadable old configuration.
    original = load_plugin_config(data_dir)
    if os.path.exists(path):
        backup = os.path.join(data_dir, "config.pre-work-mode.json")
        try:
            with open(backup, "xb") as dst, open(path, "rb") as src:
                shutil.copyfileobj(src, dst)
        except FileExistsError:
            pass
    atomic_json_write(path, deep_merge(original, cfg))


def atomic_json_write(path: str, value: dict) -> None:
    """Use a unique temporary file so concurrent saves cannot share .tmp."""
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".multica-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        # Windows scanners may briefly hold the destination without delete-share.
        # Keep the old file intact and retry only the atomic replacement.
        for attempt in range(5):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.02)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def merge_config_update(current: dict, patch: dict) -> dict:
    """Only explicit, non-placeholder credentials replace the working values."""
    updated = dict(current)
    for key, value in patch.items():
        if key not in CONFIG_DEFAULTS:
            continue
        if key in ("api_url", "token"):
            if not isinstance(value, str) or not value.strip():
                continue
            if key == "token" and "****" in value:
                continue
        updated[key] = coerce_to_default_type(value, CONFIG_DEFAULTS[key])
    if patch.get("clear_token") is True:
        updated["token"] = ""
    return updated


_TRUE_WORDS = {"1", "true", "yes", "y", "on", "是", "开", "启用"}
_FALSE_WORDS = {"0", "false", "no", "n", "off", "否", "关", "停用"}


def to_bool(value: Any, default: bool = False) -> bool:
    """把常见写法安全地转成 bool。

    注意：不能用 ``bool("false")``——非空字符串永远为 True。
    无法识别时返回 ``default``。
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        token = value.strip().lower()
        if token in _TRUE_WORDS:
            return True
        if token in _FALSE_WORDS:
            return False
    if value is None:
        return default
    return default


def coerce_to_default_type(value: Any, default: Any) -> Any:
    """按 default 的类型强转 value。"""
    if isinstance(default, bool):
        return to_bool(value, default)
    if isinstance(default, int):
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return int(default)
    if isinstance(default, float):
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return float(default)
    if isinstance(default, str):
        return str(value)
    if isinstance(default, list):
        return list(value) if isinstance(value, (list, tuple)) else list(default)
    if isinstance(default, dict):
        if default:
            src = value if isinstance(value, dict) else {}
            return {
                k: coerce_to_default_type(src.get(k), dv) for k, dv in default.items()
            }
        return dict(value) if isinstance(value, dict) else {}
    return value
