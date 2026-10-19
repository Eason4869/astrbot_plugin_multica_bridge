"""Durable per-window state, independent from connection credentials."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

from .config import atomic_json_write


def conversation_key(event) -> str:
    group = str(event.get_group_id() or "")
    return json.dumps(
        [
            str(event.get_platform_id()),
            str(event.get_self_id()),
            "group" if group else "private",
            group or str(event.get_sender_id()),
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def connection_key(cfg: dict) -> str:
    raw = json.dumps(
        [
            cfg.get("api_url"),
            cfg.get("token"),
            cfg.get("workspace_id"),
            cfg.get("project_id"),
        ]
    )
    return hashlib.sha256(raw.encode()).hexdigest()


class SessionStore:
    def __init__(self, data_dir: str):
        self.path = Path(data_dir) / "work-mode.json"
        self.records: dict[str, dict] = {}
        if self.path.exists():
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if (
                not isinstance(value, dict)
                or value.get("version") != 1
                or not isinstance(value.get("sessions"), dict)
            ):
                raise ValueError("工作模式状态文件损坏；原文件未修改")
            for key, item in value["sessions"].items():
                if not isinstance(item, dict) or not isinstance(
                    item.get("active"), bool
                ):
                    raise ValueError("工作模式会话记录损坏；原文件未修改")
                self.records[key] = item

    def get(self, key: str) -> dict:
        return deepcopy(
            self.records.get(
                key,
                {
                    "active": False,
                    "generation": 0,
                    "session_id": "",
                    "cursor": "",
                    "delivery_message": "",
                    "delivery_part": 0,
                    "seen_inputs": [],
                },
            )
        )

    def update(self, key: str, **fields) -> dict:
        record = self.get(key)
        record.update(fields)
        records = dict(self.records)
        records[key] = record
        atomic_json_write(str(self.path), {"version": 1, "sessions": records})
        self.records = records
        return deepcopy(record)

    def current(self, key: str, generation: int) -> bool:
        record = self.get(key)
        return record["active"] and record["generation"] == generation

    def commit_delivery(
        self, key: str, generation: int, message_id: str, part: int
    ) -> bool:
        if not self.current(key, generation):
            return False
        if part:
            self.update(key, delivery_message=message_id, delivery_part=part)
        else:
            self.update(key, cursor=message_id, delivery_message="", delivery_part=0)
        return True
