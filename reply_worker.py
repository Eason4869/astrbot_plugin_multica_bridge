"""Generation-checked delivery; never enters AstrBot's response decorators."""

from __future__ import annotations

import asyncio

PREFIX = "【来自 Multica｜工作模式】\n"


def reply_parts(text: str) -> list[str]:
    return [PREFIX + text[i : i + 1200] for i in range(0, len(text), 1200)] or [
        PREFIX + "本轮未返回文字。"
    ]


class ReplyWorker:
    def __init__(self, store, push, permitted=None):
        self.store, self.push = store, push
        self.permitted = permitted or (lambda record: True)
        self.tasks: dict[str, asyncio.Task] = {}

    def live(self, key: str, generation: int) -> bool:
        return self.store.current(key, generation) and self.permitted(
            self.store.get(key)
        )

    async def pump_once(self, key: str, generation: int, client) -> None:
        if not self.live(key, generation):
            return
        state = self.store.get(key)
        messages = await client.messages(state["session_id"], state["cursor"])
        # The client normally trims the cursor. Also accept full historical responses.
        if any(m.get("id") == state["cursor"] for m in messages):
            for i, m in enumerate(messages):
                if m.get("id") == state["cursor"]:
                    messages = messages[i + 1 :]
                    break
        for message in messages:
            if not self.live(key, generation):
                return
            message_id = str(message.get("id") or "")
            if not message_id:
                continue
            if message.get("role") == "assistant":
                if message.get("failure_reason"):
                    content = (
                        "本轮执行失败，请在 Multica 查看详情，或重新说明下一步操作。"
                    )
                else:
                    content = str(message.get("content") or "").strip()
                    if not content:
                        content = "本轮未返回文字，请在 Multica 查看附件或执行详情。"
                parts = reply_parts(content)
                record = self.store.get(key)
                start = (
                    record.get("delivery_part", 0)
                    if record.get("delivery_message") == message_id
                    else 0
                )
                for index in range(start, len(parts)):
                    if not self.live(key, generation):
                        return
                    await self.push(record["origin"], parts[index])
                    if not self.store.commit_delivery(
                        key, generation, message_id, index + 1
                    ):
                        return
            if not self.store.commit_delivery(key, generation, message_id, 0):
                return

    def start(self, key: str, client) -> None:
        existing = self.tasks.get(key)
        if existing and not existing.done():
            return
        generation = self.store.get(key)["generation"]
        self.tasks[key] = asyncio.create_task(self._run(key, generation, client))

    async def _run(self, key: str, generation: int, client) -> None:
        failure_reported = False
        delay = 2
        while self.live(key, generation):
            try:
                await self.pump_once(key, generation, client)
                pending = await client.pending(self.store.get(key)["session_id"])
                delay = (
                    2 if pending.get("task_id") or pending.get("queued_tasks") else 10
                )
                failure_reported = False
            except asyncio.CancelledError:
                raise
            except Exception:
                delay = min(delay * 2, 30)
                if not failure_reported and self.live(key, generation):
                    try:
                        await self.push(
                            self.store.get(key)["origin"],
                            PREFIX
                            + "回复同步暂时失败，正在重试；仍处于工作模式，/multica exit 可退出。",
                        )
                        failure_reported = True
                    except Exception:
                        pass
            await asyncio.sleep(delay)

    def cancel(self, key: str) -> None:
        task = self.tasks.pop(key, None)
        if task:
            task.cancel()

    async def close(self) -> None:
        tasks = list(self.tasks.values())
        self.tasks.clear()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
