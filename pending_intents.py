"""Short-lived, one-use issue drafts; never persisted with credentials."""

from __future__ import annotations

import secrets
from copy import deepcopy

from .actions import ActionRequest


class PendingIntentStore:
    def __init__(self):
        self.records: dict[str, tuple] = {}

    def _expire(self, now: float) -> None:
        self.records = {k: v for k, v in self.records.items() if now < v[3]}

    def create(
        self,
        owner: tuple[str, ...],
        request: ActionRequest,
        context_key: str,
        now: float,
    ) -> str:
        self._expire(now)
        self.records = {k: v for k, v in self.records.items() if v[0] != owner}
        if len(self.records) >= 1000:
            raise ValueError("待确认请求过多，请稍后重试")
        while True:
            code = f"{secrets.randbelow(1000000):06d}"
            if code not in self.records:
                break
        self.records[code] = (owner, deepcopy(request), context_key, now + 120)
        return code

    def claim(
        self, owner: tuple[str, ...], code: str, context_key: str, now: float
    ) -> ActionRequest | None:
        self._expire(now)
        record = self.records.get(code)
        if not record or record[0] != owner:
            return None
        self.records.pop(code)
        if record[2] != context_key:
            return None
        request = record[1]
        return ActionRequest(request.name, request.fields, "confirmation")

    def cancel(self, owner: tuple[str, ...], code: str) -> bool:
        record = self.records.get(code)
        if record and record[0] == owner:
            self.records.pop(code)
            return True
        return False
