import asyncio

import pytest
from test_work_mode import Event, setup_service


def test_stop_invalidates_local_queue_without_waiting_for_history(tmp_path):
    async def run():
        service, client, _ = setup_service(tmp_path)
        started, proceed = asyncio.Event(), asyncio.Event()
        tasks = []
        try:
            await service.handle(Event())
            await service.worker.close()

            async def history(*args):
                started.set()
                await proceed.wait()
                return []

            client.messages = history
            tasks.append(asyncio.create_task(service.handle(Event("old-1"))))
            await started.wait()
            tasks.append(asyncio.create_task(service.handle(Event("old-2"))))
            await asyncio.sleep(0)
            await asyncio.wait_for(service.handle(Event("/multica stop")), 0.5)
            proceed.set()
            await asyncio.gather(*tasks)
            assert not client.sent
        finally:
            proceed.set()
            await asyncio.gather(*tasks, return_exceptions=True)
            await service.close()

    asyncio.run(run())


def test_stop_waits_for_inflight_post_before_remote_cancellation(tmp_path):
    async def run():
        service, client, _ = setup_service(tmp_path)
        started, proceed = asyncio.Event(), asyncio.Event()
        trace, tasks = [], []
        try:
            await service.handle(Event())
            await service.worker.close()

            async def send(*args):
                started.set()
                await proceed.wait()
                trace.append("accepted")
                return {"message_id": "m", "task_id": "t"}

            async def stop(*args):
                trace.append("stop")

            client.send_chat, client.stop = send, stop
            tasks.append(asyncio.create_task(service.handle(Event("in flight"))))
            await started.wait()
            stopping = asyncio.create_task(service.handle(Event("/multica stop")))
            tasks.append(stopping)
            await asyncio.sleep(0)
            assert not stopping.done()
            during = Event("during stop")
            await asyncio.wait_for(service.handle(during), 0.5)
            assert during.replies
            proceed.set()
            await asyncio.gather(*tasks)
            assert trace == ["accepted", "stop"]
        finally:
            proceed.set()
            await asyncio.gather(*tasks, return_exceptions=True)
            await service.close()

    asyncio.run(run())


def test_exit_while_chat_creation_is_in_flight_cannot_reenter(tmp_path):
    async def run():
        service, client, _ = setup_service(tmp_path)
        started, proceed = asyncio.Event(), asyncio.Event()
        original = client.create_chat

        async def slow(*args):
            started.set()
            await proceed.wait()
            return await original(*args)

        client.create_chat = slow
        enter = asyncio.create_task(service.handle(Event()))
        try:
            await started.wait()
            await asyncio.wait_for(service.handle(Event("/multica exit")), 1)
            proceed.set()
            await enter
            assert not service.should_route(Event("ordinary"))
        finally:
            proceed.set()
            await service.close()

    asyncio.run(run())


def test_messages_during_enter_are_owned_until_chat_is_ready(tmp_path):
    async def run():
        service, client, _ = setup_service(tmp_path)
        started, proceed = asyncio.Event(), asyncio.Event()
        original = client.create_chat

        async def slow(*args):
            started.set()
            await proceed.wait()
            return await original(*args)

        client.create_chat = slow
        enter = asyncio.create_task(service.handle(Event()))
        try:
            await started.wait()
            assert service.should_route(Event("question while entering"))
            question = asyncio.create_task(
                service.handle(Event("question while entering"))
            )
            proceed.set()
            await asyncio.gather(enter, question)
            assert len(client.sent) == 1
        finally:
            proceed.set()
            await service.close()

    asyncio.run(run())


def test_unload_cancels_inflight_enter_without_late_state_or_worker(tmp_path):
    async def run():
        service, client, outputs = setup_service(tmp_path)
        started, proceed = asyncio.Event(), asyncio.Event()

        async def slow(*args):
            started.set()
            await proceed.wait()
            return {"id": "late-chat", "status": "active"}

        client.create_chat = slow
        event = Event()
        entering = asyncio.create_task(service.handle(event))
        await started.wait()
        await service.close()
        proceed.set()
        await asyncio.gather(entering, return_exceptions=True)
        assert not service.store.get(next(iter(service.store.records), "missing"))[
            "active"
        ]
        assert not service.worker.tasks
        assert not event.replies and not outputs

    asyncio.run(run())


def test_exit_suppresses_late_submission_error(tmp_path):
    async def run():
        service, client, _ = setup_service(tmp_path)
        started, proceed = asyncio.Event(), asyncio.Event()
        try:
            await service.handle(Event())

            async def slow(*args):
                started.set()
                await proceed.wait()
                raise RuntimeError("late failure")

            client.send_chat = slow
            event = Event("work")
            task = asyncio.create_task(service.handle(event))
            await started.wait()
            await service.handle(Event("/multica exit"))
            proceed.set()
            await task
            assert not event.replies
        finally:
            proceed.set()
            await service.close()

    asyncio.run(run())


@pytest.mark.parametrize(
    "setting,value",
    [
        ("enabled", False),
        ("work_mode_enabled", False),
        ("multica_whitelist", []),
    ],
)
def test_revoking_policy_during_history_prevents_submission(tmp_path, setting, value):
    async def run():
        service, client, _ = setup_service(tmp_path)
        try:
            await service.handle(Event())

            async def changed(*args):
                service.plugin.cfg[setting] = value
                return []

            client.messages = changed
            await service.handle(Event("do not send"))
            assert not client.sent
        finally:
            await service.close()

    asyncio.run(run())


def test_legacy_management_still_works_with_work_mode_disabled(tmp_path):
    async def run():
        service, _, _ = setup_service(tmp_path)
        calls = []

        async def dispatch(event, tail):
            calls.append(tail)

        service.plugin.dispatch_legacy = dispatch
        service.plugin.cfg["work_mode_enabled"] = False
        try:
            await service.handle(Event("/multica inbox"))
            assert calls == ["inbox"]
        finally:
            await service.close()

    asyncio.run(run())


def test_timed_out_submission_is_reconciled_without_resending(tmp_path):
    async def run():
        from astrbot_plugin_multica_bridge.chat_client import MulticaError

        service, client, _ = setup_service(tmp_path)
        try:
            await service.handle(Event())
            calls = []

            async def timed_out(session, content):
                calls.append(content)
                client.history.append(
                    {"id": "accepted-1", "role": "user", "content": content}
                )
                raise MulticaError("request timed out", uncertain=True)

            client.send_chat = timed_out
            await service.handle(Event("do work", message_id="q1"))
            await service.handle(Event("do work", message_id="q1"))
            assert len(calls) == 1
            assert not service.store.get(next(iter(service.store.records))).get(
                "uncertain"
            )
        finally:
            await service.close()

    asyncio.run(run())


def test_connection_change_during_enter_does_not_bind_old_chat_to_new_server(tmp_path):
    async def run():
        service, client, _ = setup_service(tmp_path)
        original = client.create_chat

        async def changed(*args):
            service.plugin.cfg["api_url"] = "https://different.example.test"
            return await original(*args)

        client.create_chat = changed
        try:
            await service.handle(Event())
            assert not service.should_route(Event("ordinary"))
        finally:
            await service.close()

    asyncio.run(run())


def test_uncertain_submission_does_not_match_identical_old_user_message(tmp_path):
    async def run():
        from astrbot_plugin_multica_bridge.chat_client import MulticaError
        from astrbot_plugin_multica_bridge.session_store import conversation_key

        service, client, _ = setup_service(tmp_path)
        try:
            await service.handle(Event())
            key = conversation_key(Event())
            client.history = [
                {"id": "old", "role": "user", "content": "[u1 / QQ u1]\nsame request"}
            ]
            service.store.update(key, cursor="old")

            async def history(session, since_id=""):
                return [] if since_id == "old" else list(client.history)

            client.messages = history

            async def no_accept(session, content):
                raise MulticaError("timed out before receipt", uncertain=True)

            client.send_chat = no_accept
            await service.handle(Event("same request", message_id="new-request"))
            await service.handle(Event("same request", message_id="new-request"))
            assert service.store.get(key).get("uncertain")
        finally:
            await service.close()

    asyncio.run(run())
