from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.runtime.system.sessions import SessionStore

if TYPE_CHECKING:
    from app.core.runtime.chat.chat_runtime import ChatRuntime


class SessionPersistHook:
    order = 450

    def __init__(self, session_store: SessionStore) -> None:
        self.session_store = session_store

    def run(self, state: "ChatRuntime") -> None:
        if state.skip_session_persist:
            return
        snapshot = self.session_store.save_turn(
            session_id=state.session_id,
            user_id=state.user_id,
            user_text=state.query,
            assistant_text=state.final_response,
            agent_name=state.current_agent,
        )
        if snapshot.session_id and snapshot.user_id and snapshot.user_id != state.user_id:
            state.artifacts["session_owner_mismatch"] = True
            return
        state.artifacts["session_snapshot"] = snapshot
        state.artifacts["session_recent_turns"] = len(snapshot.recent_turns)

