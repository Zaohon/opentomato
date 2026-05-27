from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.core.runtime.system.sessions import SessionStore

if TYPE_CHECKING:
    from app.core.runtime.chat.chat_runtime import ChatRuntime

logger = get_logger("app.runtime.session_hook")


class SessionLoadHook:
    order = 110

    def __init__(self, session_store: SessionStore) -> None:
        self.session_store = session_store

    def run(self, state: "ChatRuntime") -> None:
        if state.skip_session_load:
            logger.info("skip_session_load user=%s session=%s", state.user_id, state.session_id)
            return
        snapshot = self.session_store.load(state.session_id, user_id=state.user_id)
        if snapshot.session_id and snapshot.user_id and snapshot.user_id != state.user_id:
            state.artifacts["session_owner_mismatch"] = True
            logger.warning(f"[SessionLoad] Owner mismatch user={state.user_id} session={state.session_id}")
            return
        state.artifacts["session_snapshot"] = snapshot
        state.artifacts["session_recent_turns"] = len(snapshot.recent_turns)
        state.artifacts["session_summary_loaded"] = bool(snapshot.summary)
        if not state.chat_history and snapshot.recent_turns:
            state.chat_history = list(snapshot.recent_turns)
        if snapshot.summary and not state.ctx.rag_context:
            state.ctx.rag_context = (
                "[SESSION SUMMARY]\n"
                f"last_agent: {snapshot.last_agent or 'unknown'}\n"
                f"{snapshot.summary}"
            )
        history_msgs, history_chars = self._history_metrics(state.chat_history)
        state.artifacts["history_msgs"] = history_msgs
        state.artifacts["history_chars"] = history_chars
        logger.info(
            "loaded_history user=%s history_msgs=%s history_chars=%s memory_summary=%s",
            state.user_id,
            history_msgs,
            history_chars,
            "loaded" if state.memory_summary_md else "empty",
        )

    @staticmethod
    def _history_chars(history_messages: object) -> int:
        total = 0
        if not isinstance(history_messages, list):
            return total
        for item in history_messages:
            if not isinstance(item, dict):
                continue
            total += len(str(item.get("content", "") or ""))
        return total

    def _history_metrics(self, history_messages: object) -> tuple[int, int]:
        msgs = len(history_messages) if isinstance(history_messages, list) else 0
        chars = self._history_chars(history_messages)
        return msgs, chars
