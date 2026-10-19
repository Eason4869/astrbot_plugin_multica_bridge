"""Per-window work-mode commands and direct Chat submission."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time

from .chat_client import ChatClient, MulticaError
from .reply_worker import ReplyWorker, reply_parts
from .session_store import connection_key, conversation_key

COMMAND = re.compile(r"^/multica(?:\s+(.*))?$", re.IGNORECASE | re.DOTALL)
CONTROLS = {"enter", "exit", "new", "agent", "stop", "status", "help"}
ACK_DELAY = 2


class WorkMode:
    def __init__(self, plugin, store, say, push, client_factory=ChatClient):
        self.plugin, self.store, self.say = plugin, store, say
        self.client_factory = client_factory
        self.locks: dict[str, asyncio.Lock] = {}
        self.opening: dict[str, set[object]] = {}
        self.opening_owners: dict[str, str] = {}
        self.submission_epochs: dict[str, int] = {}
        self.stopping: set[str] = set()
        self.submissions: dict[str, asyncio.Task] = {}
        self.ack_tasks: set[asyncio.Task] = set()
        self.operations: set[asyncio.Task] = set()
        self.worker = ReplyWorker(store, push, self._delivery_permitted)
        self.closed = False
        self.log = getattr(plugin, "log", logging.getLogger(__name__))

    def _delivery_permitted(self, record: dict) -> bool:
        if self.closed:
            return False
        cfg = self.plugin.cfg
        if not cfg.get("enabled", True) or not cfg.get("work_mode_enabled", True):
            return False
        if record.get("connection") != connection_key(cfg):
            return False
        from .multica_client import check_chat_allowed

        return any(
            check_chat_allowed(cfg, "user", record.get("owner_id", ""), origin)
            for origin in record.get(
                "access_origins",
                [record.get("access_origin", record.get("origin", ""))],
            )
        )

    def should_route(self, event) -> bool:
        key = conversation_key(event)
        state = self.store.get(key)
        owner = state.get("owner_id") or self.opening_owners.get(key)
        return (
            bool(COMMAND.fullmatch((event.message_str or "").strip()))
            or bool(getattr(event, "_multica_nl_enter", False))
            or (not state["active"] and self._natural_enter(event))
            or (
                (bool(self.opening.get(key)) or state["active"])
                and bool(owner)
                and owner == str(event.get_sender_id())
            )
        )

    def _natural_enter(self, event) -> bool:
        from .structured_nl import parse_work_enter

        cfg = self.plugin.cfg
        return bool(
            cfg.get("nl_enabled", True)
            and parse_work_enter(
                str(event.message_str or ""), str(cfg.get("nl_keyword") or "multica")
            ).request
        )

    async def enter_from_intent(self, event) -> None:
        router = getattr(self.plugin, "_work_router", None)
        if not router or not hasattr(event, "_multica_scheduler"):
            await self.reply(
                event,
                "当前无法安全接管消息，未进入工作模式。请使用 /multica 或检查插件日志。",
            )
            return
        event._multica_nl_enter = True
        await router._owned(event._multica_scheduler, event)

    async def reply(self, event, text: str) -> None:
        for part in reply_parts(text):
            key = getattr(event, "_multica_key", None)
            if self.closed or (
                key is not None
                and self.store.get(key)["generation"] != event._multica_generation
            ):
                return
            await self.say(event, part)

    def resume(self) -> None:
        for key in self.store.records:
            state = self.store.get(key)
            if (
                state["active"]
                and state.get("session_id")
                and self._delivery_permitted(state)
            ):
                cfg = dict(self.plugin.cfg, workspace_id=state["workspace_id"])
                self.worker.start(key, self.client_factory(cfg))

    def refresh(self) -> None:
        for key in list(self.worker.tasks):
            self.worker.cancel(key)
        self.resume()

    async def handle(self, event) -> None:
        if self.closed:
            event.stop_event()
            return
        key = conversation_key(event)
        if not self.should_route(event):
            return
        text = (event.message_str or "").strip()
        matched = COMMAND.fullmatch(text)
        tail = (matched.group(1) or "").strip() if matched else ""
        pieces = tail.split(maxsplit=1)
        control, args = (
            (pieces[0], pieces[1] if len(pieces) > 1 else "") if pieces else ("", "")
        )
        control = control.casefold() if matched else ""
        control = control or ("enter" if matched else "")
        if not matched and (
            getattr(event, "_multica_nl_enter", False)
            or (not self.store.get(key)["active"] and self._natural_enter(event))
        ):
            control = "enter"
        state = self.store.get(key)
        owner = (
            state.get("owner_id") if state["active"] else self.opening_owners.get(key)
        )
        if (
            owner
            and owner != str(event.get_sender_id())
            and control in {"enter", "exit", "new", "agent", "stop"}
        ):
            await self.reply(
                event,
                "本群工作会话由其他成员开启，仅开启者可发送或控制；你的普通消息继续由 AstrBot 处理。",
            )
            event.stop_event()
            return
        if key in self.stopping and control != "exit":
            await self.reply(event, "正在停止执行，请稍后重试。")
            event.stop_event()
            return
        event._multica_submit_epoch = self.submission_epochs.get(key, 0)
        operation = asyncio.current_task()
        started = time.monotonic()
        self.operations.add(operation)
        event._multica_key = key
        event._multica_generation = self.store.get(key)["generation"] + (
            1 if not matched and self.opening.get(key) else 0
        )
        opening_token = object() if control in {"enter", "new", "agent"} else None
        if opening_token:
            self.opening.setdefault(key, set()).add(opening_token)
            self.opening_owners[key] = str(event.get_sender_id())
        try:
            if control == "exit":
                self.submission_epochs[key] = self.submission_epochs.get(key, 0) + 1
                state = self.store.get(key)
                self.store.update(key, active=False, generation=state["generation"] + 1)
                event._multica_generation = state["generation"] + 1
                self.opening.pop(key, None)
                self.worker.cancel(key)
                await self.reply(
                    event,
                    "已退出工作模式，恢复普通机器人。Multica 已接收的任务继续运行，后续结果请在 Multica 查看。",
                )
                return
            if control == "stop":
                await self._stop(event, key)
                return
            legacy = matched and (
                control not in CONTROLS or control in {"help", "status", "stop"}
            )
            if not self.plugin.cfg.get("enabled", True) or (
                not legacy and not self.plugin.cfg.get("work_mode_enabled", True)
            ):
                await self.reply(
                    event, "工作模式已停用；/multica exit 可退出当前模式。"
                )
                return
            # Exit is deliberately outside this lock: remote calls must not block escape.
            async with self.locks.setdefault(key, asyncio.Lock()):
                if (
                    self.closed
                    or self.store.get(key)["generation"] != event._multica_generation
                    or event._multica_submit_epoch != self.submission_epochs.get(key, 0)
                ):
                    return
                if control == "agent" and not args:
                    agents = await self.client_factory(
                        dict(self.plugin.cfg)
                    ).list_agents()
                    self.store.update(key, agent_choices=[a["id"] for a in agents])
                    await self.reply(
                        event,
                        "请选择智能体，发送 /multica agent <编号或ID>：\n"
                        + "\n".join(
                            f"{i + 1}. {a.get('name') or a['id']}"
                            for i, a in enumerate(agents)
                        ),
                    )
                elif control in {"enter", "new", "agent"}:
                    await self._enter(
                        event,
                        key,
                        fresh=control in {"new", "agent"},
                        choice=args if control == "agent" else "",
                    )
                elif control == "help":
                    from .actions import help_text

                    await self.reply(
                        event,
                        help_text(),
                    )
                elif control == "status":
                    await self._status(event, key)
                elif matched:
                    dispatch = getattr(self.plugin, "dispatch_legacy", None)
                    if dispatch:
                        await dispatch(event, tail)
                    else:
                        await self.reply(event, "未知命令，请使用 /multica help。")
                else:
                    await self._submit(event, key, text)
        except MulticaError as exc:
            self.log.warning(
                "[multica_bridge] stage=%s exception=%s status=%d uncertain=%s elapsed=%.2fs",
                control or "submit",
                type(exc).__name__,
                exc.status,
                exc.uncertain,
                time.monotonic() - started,
            )
            mode_hint = (
                "仍处于工作模式；/multica exit 可退出。"
                if self.store.get(key)["active"]
                else "尚未进入工作模式，当前仍是普通模式，请修复后重试。"
            )
            await self.reply(event, f"{exc}。{mode_hint}")
        except Exception as exc:
            self.log.warning(
                "[multica_bridge] stage=%s exception=%s elapsed=%.2fs",
                control or "submit",
                type(exc).__name__,
                time.monotonic() - started,
            )
            await self.reply(
                event,
                "本次操作失败，请检查连接或查看插件日志。工作模式不会自动切回普通模型；/multica exit 可退出。",
            )
        finally:
            self.operations.discard(operation)
            tokens = self.opening.get(key)
            if tokens and opening_token in tokens:
                tokens.discard(opening_token)
                if not tokens:
                    self.opening.pop(key, None)
                    self.opening_owners.pop(key, None)
            event.stop_event()

    async def _stop(self, event, key: str) -> None:
        self.submission_epochs[key] = self.submission_epochs.get(key, 0) + 1
        state = self.store.get(key)
        if not state.get("session_id"):
            await self.reply(
                event,
                "本地旧排队消息已丢弃；当前没有绑定的 Multica 对话，正在创建的远端会话结果尚待确认。"
                if self.opening.get(key)
                else "本地旧排队消息已丢弃；当前没有绑定的 Multica 对话。",
            )
            return
        self.stopping.add(key)
        try:
            inflight = self.submissions.get(key)
            if inflight:
                try:
                    await asyncio.shield(inflight)
                except MulticaError:
                    pass
            if self.store.get(key)["generation"] != event._multica_generation:
                return
            self._require_current_permission(event)
            await self._client(state).stop(state["session_id"])
            uncertain = self.store.get(key).get("uncertain")
            await self.reply(
                event,
                "已请求停止远端执行，本地旧排队消息已丢弃；仍处于工作模式。"
                + ("上一条提交结果仍待确认，请在 Multica 核对。" if uncertain else ""),
            )
        finally:
            self.stopping.discard(key)

    def _client(self, state: dict):
        if state.get("connection") != connection_key(self.plugin.cfg):
            raise MulticaError("连接或项目配置已变化，请用 /multica new 建立新绑定")
        return self.client_factory(
            dict(self.plugin.cfg, workspace_id=state["workspace_id"])
        )

    def _require_current_permission(self, event) -> None:
        authorize = getattr(self.plugin, "authorize_work_event", None)
        if authorize:
            try:
                cfg = self.plugin.context.get_config(event.unified_msg_origin)
                allowed = authorize(event, cfg)
            except Exception:
                allowed = False
            if not allowed:
                raise MulticaError("权限不足或指令已停用，未执行此 Multica 操作")

    async def _enter(self, event, key: str, fresh: bool, choice: str) -> None:
        previous = self.store.get(key)
        if previous.get("owner_migration_required") and not fresh:
            raise MulticaError(
                "旧共享会话缺少开启者信息，已暂停。请用 /multica new 新建仅本人可发送的会话"
            )
        if previous.get("owner_id") and previous["owner_id"] != str(
            event.get_sender_id()
        ):
            fresh = True
        generation = previous["generation"]
        settings = dict(self.plugin.cfg)
        fingerprint = connection_key(settings)
        group_id = str(event.get_group_id() or "")
        policy = {
            "connection": fingerprint,
            "owner_id": str(event.get_sender_id()),
            "access_origin": str(event.unified_msg_origin),
            "chat_type": "group" if group_id else "private",
            "chat_id": group_id or str(event.get_sender_id()),
        }
        from .multica_client import event_access_origins

        policy["access_origins"] = event_access_origins(event)
        if previous["active"] and previous.get("session_id") and not fresh:
            await self._status(event, key)
            return
        client = self.client_factory(settings)
        if previous.get("session_id") and not fresh:
            client = self._client(previous)
            chat = await client.get_chat(previous["session_id"])
            if chat.get("status") != "active":
                raise MulticaError("原对话不可用，请使用 /multica new")
            # Replies produced while exited stay in Multica, rather than surprising QQ.
            history = await client.messages(previous["session_id"], previous["cursor"])
            if self.store.get(key)["generation"] != generation:
                return
            if connection_key(self.plugin.cfg) != fingerprint:
                raise MulticaError("连接配置已变化，请重新进入工作模式")
            if not self._delivery_permitted(policy):
                raise MulticaError("工作转发已暂停，请检查开关和访问规则")
            self._require_current_permission(event)
            current = self.store.update(
                key,
                active=True,
                generation=generation + 1,
                cursor=str(history[-1]["id"]) if history else previous["cursor"],
            )
        else:
            agents = await client.list_agents()
            wanted = choice.strip() or str(
                self.plugin.cfg.get("default_agent_id")
                or previous.get("agent_id")
                or ""
            )
            selected = None
            if choice.strip().isdigit():
                choices = previous.get("agent_choices") or []
                position = int(choice.strip()) - 1
                if 0 <= position < len(choices):
                    wanted = choices[position]
            if wanted:
                selected = next((a for a in agents if a["id"] == wanted), None)
                if not selected:
                    raise MulticaError("指定智能体不在可用列表中，请重新选择")
            elif len(agents) == 1:
                selected = agents[0]
            if not selected:
                self.store.update(key, agent_choices=[a["id"] for a in agents])
                listing = "\n".join(
                    f"{i + 1}. {a.get('name') or a['id']}" for i, a in enumerate(agents)
                )
                await self.reply(
                    event,
                    "请选择智能体，发送 /multica agent <编号>：\n"
                    + (listing or "没有可用智能体，请先在 Multica 创建。"),
                )
                return
            if connection_key(self.plugin.cfg) != fingerprint:
                raise MulticaError("连接配置已变化，请重新进入工作模式")
            if not self._delivery_permitted(policy):
                raise MulticaError("工作转发已暂停，请检查开关和访问规则")
            self._require_current_permission(event)

            def write_guard():
                self._require_current_permission(event)
                if connection_key(
                    self.plugin.cfg
                ) != fingerprint or not self._delivery_permitted(policy):
                    raise MulticaError("配置或访问规则已变化，未创建工作对话")
                if self.store.get(key)["generation"] != generation:
                    raise MulticaError("工作会话已变化，未创建工作对话")

            client.write_guard = write_guard
            chat = await client.create_chat(
                selected["id"],
                "QQ 工作对话",
                str(settings.get("project_id") or ""),
            )
            if not chat.get("id"):
                raise MulticaError("创建对话的响应缺少会话 ID", uncertain=True)
            if self.store.get(key)["generation"] != generation:
                return
            if connection_key(self.plugin.cfg) != fingerprint:
                raise MulticaError("连接配置已变化，未绑定旧服务器的对话，请重新进入")
            if not self._delivery_permitted(policy):
                raise MulticaError("工作转发已暂停，请检查开关和访问规则")
            self._require_current_permission(event)
            group = str(event.get_group_id() or "")
            origin = event.unified_msg_origin
            if group:
                origin = f"{event.get_platform_id()}:{event.get_message_type().value}:{group}"
            self.worker.cancel(key)
            current = self.store.update(
                key,
                active=True,
                generation=generation + 1,
                session_id=chat["id"],
                agent_id=selected["id"],
                agent_name=selected.get("name") or selected["id"],
                owner_id=str(event.get_sender_id()),
                access_origin=str(event.unified_msg_origin),
                access_origins=event_access_origins(event),
                owner_migration_required=False,
                workspace_id=client._workspace_id,
                connection=fingerprint,
                origin=origin,
                chat_type="group" if group else "private",
                chat_id=group or str(event.get_sender_id()),
                cursor="",
                delivery_message="",
                delivery_part=0,
                seen_inputs=[],
                uncertain=None,
            )
        event._multica_generation = current["generation"]
        self.worker.start(key, client)
        scope = (
            "仅开启者的消息转发，其他群友继续使用 AstrBot；回复在群内可见"
            if event.get_group_id()
            else "当前私聊"
        )
        await self.reply(
            event,
            f"已进入 Multica 工作模式（{scope}）。\n智能体：{current.get('agent_name', '')}\n项目：{self.plugin.cfg.get('project_id') or '未指定'}\n后续消息直接交给 Multica；/multica exit 退出，/multica new 开新对话。",
        )

    async def _status(self, event, key: str) -> None:
        state = self.store.get(key)
        if not state.get("session_id"):
            original_status = getattr(self.plugin, "_cmd_status", None)
            if original_status:
                await original_status(event)
                return
            await self.reply(event, "当前未绑定对话，发送 /multica 开始。")
            return
        pending = await self._client(state).pending(state["session_id"])
        await self.reply(
            event,
            f"当前模式：{'工作模式' if state['active'] else '普通模式'}\n连接：正常\n智能体：{state.get('agent_name', '')}\n工作区：{state.get('workspace_id', '')}\n项目：{self.plugin.cfg.get('project_id') or '未指定'}\n执行状态：{pending.get('status') or '空闲'}\n/multica exit 退出。",
        )

    async def _submit(self, event, key: str, text: str) -> None:
        deliveries_before = self.worker.deliveries.get(key, 0)
        state = self.store.get(key)
        if not state["active"]:
            return
        if state.get("owner_id") != str(event.get_sender_id()):
            return
        # Do not transcribe audio or silently drop attachments from mixed messages.
        components = event.get_messages()
        if not text or any(
            type(c).__name__ not in {"Plain", "At", "AtAll", "Reply"}
            for c in components
        ):
            await self.reply(
                event,
                "当前支持文字对话；图片、文件、语音请在 Multica 中发送。仍处于工作模式。",
            )
            return
        client = self._client(state)
        identity = str(getattr(event.message_obj, "message_id", "") or "")
        input_id = f"{event.get_sender_id()}:{identity}" if identity else ""
        if input_id and input_id in state.get("seen_inputs", []):
            return
        if state.get("uncertain"):
            pending = state["uncertain"]
            history = await client.messages(
                state["session_id"], pending.get("before_id", "")
            )
            matches = [
                m
                for m in history
                if m.get("role") == "user"
                and hashlib.sha256(str(m.get("content") or "").encode()).hexdigest()
                == pending.get("digest")
            ]
            if len(matches) != 1:
                await self.reply(
                    event,
                    "上一条提交结果待确认，未自动重发。请在 Multica 核对后使用 /multica new，或 /multica exit 退出。",
                )
                return
            if not self.store.current(key, state["generation"]):
                return
            seen = state.get("seen_inputs", [])
            if pending.get("input_id"):
                seen = (seen + [pending["input_id"]])[-200:]
            state = self.store.update(key, uncertain=None, seen_inputs=seen)
            self.worker.start(key, client)
            await self.reply(
                event, "已核对：上一条消息已被 Multica 接收，没有重复提交。"
            )
            if input_id and input_id in seen:
                return
        generation = state["generation"]
        content = (
            f"[{event.get_sender_name()} / QQ {event.get_sender_id()}]\n{text}"
            if event.get_group_id()
            else text
        )
        history = await client.messages(state["session_id"], state["cursor"])
        if not self.store.current(key, generation):
            return
        if event._multica_submit_epoch != self.submission_epochs.get(key, 0):
            return
        self._client(state)  # Revalidate after the await, before any external write.
        if not self._delivery_permitted(state):
            raise MulticaError("工作转发已暂停，请检查开关和访问规则")
        self._require_current_permission(event)
        self.store.update(
            key,
            uncertain={
                "input_id": input_id,
                "digest": hashlib.sha256(content.encode()).hexdigest(),
                "before_id": str(history[-1]["id"]) if history else state["cursor"],
            },
        )
        try:
            submission = asyncio.create_task(
                client.send_chat(state["session_id"], content)
            )
            self.submissions[key] = submission
            try:
                result = await submission
            finally:
                if self.submissions.get(key) is submission:
                    self.submissions.pop(key, None)
        except MulticaError as exc:
            if not exc.uncertain and self.store.current(key, generation):
                self.store.update(key, uncertain=None)
            raise
        if not self.store.current(key, generation):
            return
        seen = state.get("seen_inputs", [])
        if input_id:
            seen = (seen + [input_id])[-200:]
        self.store.update(key, uncertain=None, seen_inputs=seen)
        self.worker.start(key, client)
        if result.get("queued"):
            await self.reply(event, "已交给 Multica，正在排队。")
        else:

            async def acknowledge():
                await asyncio.sleep(ACK_DELAY)
                if self.worker.deliveries.get(key, 0) == deliveries_before:
                    await self.reply(event, "已交给 Multica，等待回复。")

            task = asyncio.create_task(acknowledge())
            self.ack_tasks.add(task)
            task.add_done_callback(self.ack_tasks.discard)

    async def close(self) -> None:
        self.closed = True
        for task in self.ack_tasks:
            task.cancel()
        await asyncio.gather(*self.ack_tasks, return_exceptions=True)
        operations = [
            task for task in self.operations if task is not asyncio.current_task()
        ]
        for task in operations:
            task.cancel()
        await asyncio.gather(*operations, return_exceptions=True)
        await self.worker.close()
