"""Multica 桥接插件配置。

配置结构：CONFIG_DEFAULTS 定义所有配置项及其默认值，
AstrBot 的 _conf_schema.json 仅保留开关 enabled，其余所有参数存入插件自有 config.json，
不受 schema 裁剪影响。
"""

from __future__ import annotations

import json
import os
from typing import Any

CONFIG_DEFAULTS: dict[str, Any] = {
    "enabled": True,
    "api_url": "http://localhost:8080",
    "token": "",
    "workspace_id": "",
    "project_id": "",
    "sync_reports": False,
    "sync_interval_minutes": 60,
    # 群聊黑白名单
    "group_chat_mode": "blacklist",  # "blacklist" | "whitelist" | "disabled"
    "group_chat_list": [],
    # 私聊黑白名单
    "private_chat_mode": "blacklist",  # "blacklist" | "whitelist" | "disabled"
    "private_chat_list": [],
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
    try:
        path = os.path.join(data_dir, "config.json")
        if not os.path.exists(path):
            return {}
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_plugin_config(data_dir: str, cfg: dict[str, Any]) -> None:
    """原子写插件自有配置文件。"""
    path = os.path.join(data_dir, "config.json")
    tmp = path + ".tmp"
    os.makedirs(data_dir, exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2, default=str)
    os.replace(tmp, path)


def coerce_to_default_type(value: Any, default: Any) -> Any:
    """按 default 的类型强转 value。"""
    if isinstance(default, bool):
        return bool(value)
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
            return {k: coerce_to_default_type(src.get(k), dv) for k, dv in default.items()}
        return dict(value) if isinstance(value, dict) else {}
    return value
