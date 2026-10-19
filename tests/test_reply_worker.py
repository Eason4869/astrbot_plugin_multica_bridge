import asyncio
import importlib

from astrbot_plugin_multica_bridge.session_store import SessionStore


def test_reply_prefix_dedup_empty_failure_and_stale_generation(tmp_path):
    async def run():
        worker_module = importlib.import_module(
            "astrbot_plugin_multica_bridge.reply_worker"
        )
        from test_work_mode import Client

        store = SessionStore(str(tmp_path))
        state = store.update(
            "room",
            active=True,
            origin="qq:GroupMessage:A",
            session_id="chat",
            generation=1,
        )
        client = Client()
        client.history = [
            {"id": "r1", "role": "assistant", "content": "结果" * 1500},
            {
                "id": "r2",
                "role": "assistant",
                "content": "",
                "message_kind": "no_response",
            },
            {
                "id": "r3",
                "role": "assistant",
                "content": "RAW PRIVATE ERROR",
                "failure_reason": "timeout",
            },
        ]
        outputs = []

        async def push(origin, text):
            outputs.append((origin, text))

        worker = worker_module.ReplyWorker(store, push)
        await worker.pump_once("room", state["generation"], client)
        count = len(outputs)
        assert count >= 5
        assert all(text.startswith("【来自 Multica｜工作模式】") for _, text in outputs)
        assert all(len(text) <= 1300 for _, text in outputs)
        assert "RAW PRIVATE" not in "".join(text for _, text in outputs)
        await worker.pump_once("room", state["generation"], client)
        assert len(outputs) == count
        store.update("room", active=False, generation=2)
        client.history.append({"id": "r4", "role": "assistant", "content": "late"})
        await worker.pump_once("room", 1, client)
        assert len(outputs) == count

    asyncio.run(run())


def test_exit_during_split_reply_stops_remaining_parts(tmp_path):
    async def run():
        module = importlib.import_module("astrbot_plugin_multica_bridge.reply_worker")
        from test_work_mode import Client

        store = SessionStore(str(tmp_path))
        store.update(
            "room",
            active=True,
            session_id="chat",
            origin="qq:GroupMessage:A",
            generation=1,
        )
        client = Client()
        client.history = [{"id": "r1", "role": "assistant", "content": "x" * 4000}]
        outputs = []

        async def push(origin, text):
            outputs.append(text)
            store.update("room", active=False, generation=2)

        await module.ReplyWorker(store, push).pump_once("room", 1, client)
        assert len(outputs) == 1

    asyncio.run(run())
