from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Protocol


@dataclass
class SessionSnapshot:
    session_id: str
    user_id: str
    recent_turns: List[Dict[str, str]] = field(default_factory=list)
    summary: str = ""
    last_agent: str = ""
    updated_at: float = 0.0


class SessionStore(Protocol):
    def load(self, session_id: str, *, user_id: str) -> SessionSnapshot:
        ...

    def load_latest(self, *, user_id: str) -> SessionSnapshot:
        ...

    def save_turn(
        self,
        *,
        session_id: str,
        user_id: str,
        user_text: str,
        assistant_text: str,
        agent_name: str,
        max_turns: int = 30,
    ) -> SessionSnapshot:
        ...

    def clear(self, *, user_id: str, session_id: str = "") -> SessionSnapshot:
        ...


class InMemorySessionStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: Dict[str, SessionSnapshot] = {}
        self._latest_by_user: Dict[str, str] = {}

    def load(self, session_id: str, *, user_id: str) -> SessionSnapshot:
        safe_session = str(session_id or "").strip()
        safe_user = str(user_id or "").strip()
        if not safe_session or not safe_user:
            return SessionSnapshot(session_id="", user_id="")
        with self._lock:
            snapshot = self._items.get(safe_session)
            if snapshot is None:
                snapshot = SessionSnapshot(session_id=safe_session, user_id=safe_user)
                self._items[safe_session] = snapshot
            elif snapshot.user_id != safe_user:
                return SessionSnapshot(session_id="", user_id="")
            return SessionSnapshot(
                session_id=snapshot.session_id,
                user_id=snapshot.user_id,
                recent_turns=list(snapshot.recent_turns),
                summary=snapshot.summary,
                last_agent=snapshot.last_agent,
                updated_at=snapshot.updated_at,
            )

    def load_latest(self, *, user_id: str) -> SessionSnapshot:
        safe_user = str(user_id or "").strip()
        if not safe_user:
            return SessionSnapshot(session_id="", user_id="")
        with self._lock:
            latest_session_id = str(self._latest_by_user.get(safe_user, "") or "").strip()
            if latest_session_id:
                snapshot = self._items.get(latest_session_id)
                if snapshot is not None and snapshot.user_id == safe_user:
                    return SessionSnapshot(
                        session_id=snapshot.session_id,
                        user_id=snapshot.user_id,
                        recent_turns=list(snapshot.recent_turns),
                        summary=snapshot.summary,
                        last_agent=snapshot.last_agent,
                        updated_at=snapshot.updated_at,
                    )
            for snapshot in self._items.values():
                if snapshot.user_id != safe_user:
                    continue
                self._latest_by_user[safe_user] = snapshot.session_id
                return SessionSnapshot(
                    session_id=snapshot.session_id,
                    user_id=snapshot.user_id,
                    recent_turns=list(snapshot.recent_turns),
                    summary=snapshot.summary,
                    last_agent=snapshot.last_agent,
                    updated_at=snapshot.updated_at,
                )
        return SessionSnapshot(session_id="", user_id=safe_user)

    def save_turn(
        self,
        *,
        session_id: str,
        user_id: str,
        user_text: str,
        assistant_text: str,
        agent_name: str,
        max_turns: int = 30,
    ) -> SessionSnapshot:
        safe_session = str(session_id or "").strip()
        safe_user = str(user_id or "").strip()
        if not safe_session or not safe_user:
            return SessionSnapshot(session_id="", user_id="")

        now = time.time()
        with self._lock:
            snapshot = self._items.get(safe_session) or SessionSnapshot(session_id=safe_session, user_id=safe_user)
            if snapshot.user_id and snapshot.user_id != safe_user:
                return SessionSnapshot(session_id="", user_id="")
            turns = list(snapshot.recent_turns)
            if user_text.strip():
                turns.append({"role": "user", "content": user_text.strip()})
            if assistant_text.strip():
                turns.append({"role": "assistant", "content": assistant_text.strip()})
            max_messages = max(max_turns * 2, 2)
            if len(turns) > max_messages:
                turns = turns[-max_messages:]
            summary = self._build_summary(turns)
            updated = SessionSnapshot(
                session_id=safe_session,
                user_id=safe_user,
                recent_turns=turns,
                summary=summary,
                last_agent=agent_name.strip(),
                updated_at=now,
            )
            self._items[safe_session] = updated
            self._latest_by_user[safe_user] = safe_session
            return SessionSnapshot(
                session_id=updated.session_id,
                user_id=updated.user_id,
                recent_turns=list(updated.recent_turns),
                summary=updated.summary,
                last_agent=updated.last_agent,
                updated_at=updated.updated_at,
            )

    def clear(self, *, user_id: str, session_id: str = "") -> SessionSnapshot:
        safe_user = str(user_id or "").strip()
        safe_session = str(session_id or "").strip()
        if not safe_user:
            return SessionSnapshot(session_id="", user_id="")

        with self._lock:
            resolved_session = safe_session or str(self._latest_by_user.get(safe_user, "") or "").strip()
            if not resolved_session:
                return SessionSnapshot(session_id="", user_id=safe_user)

            snapshot = self._items.get(resolved_session)
            if snapshot is not None and snapshot.user_id != safe_user:
                return SessionSnapshot(session_id="", user_id="")

            removed = self._items.pop(resolved_session, None)
            latest_session = str(self._latest_by_user.get(safe_user, "") or "").strip()
            if latest_session == resolved_session:
                self._latest_by_user.pop(safe_user, None)

            if removed is None:
                return SessionSnapshot(session_id=resolved_session, user_id=safe_user)
            return SessionSnapshot(
                session_id=removed.session_id,
                user_id=removed.user_id,
                recent_turns=list(removed.recent_turns),
                summary=removed.summary,
                last_agent=removed.last_agent,
                updated_at=removed.updated_at,
            )

    @staticmethod
    def _build_summary(turns: List[Dict[str, str]]) -> str:
        if not turns:
            return ""
        parts: List[str] = []
        for item in turns[-4:]:
            role = str(item.get("role", "") or "").strip()
            content = " ".join(str(item.get("content", "") or "").split())
            if not role or not content:
                continue
            parts.append(f"{role}: {content[:120]}")
        return "\n".join(parts)
