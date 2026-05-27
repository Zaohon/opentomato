import hashlib
import re
import time
import threading
from typing import Any, Dict, Optional

from app.core.config.user_id import normalize_user_id
from app.core.logging import get_logger
from .client import OpenVikingClientBase
from .openviking_api import OpenVikingAPI

logger = get_logger("app.memory.openviking.content")


class OpenVikingContentProvider(OpenVikingClientBase):
    _USER_PATH_PATTERN = re.compile(r"^viking://user/([^/]+)/")
    _RESOURCES_USER_PATTERN = re.compile(r"/users/([^/]+)(?:/|$)")
    _MEMORY_SESSION_PREFIX = "memory_session"

    def _is_user_scope_guard_blocked(
        self,
        uri: str,
        *,
        user_id: Optional[str],
        api_key: Optional[str],
    ) -> bool:
        """
        Guard user-key requests from accidentally accessing another user's explicit URI.
        Applies only when using per-user key flow (user_id provided, api_key not provided).
        """
        if not user_id or api_key:
            return False
        normalized = (uri or "").strip()
        if not normalized.startswith("viking://"):
            return False

        safe_user = normalize_user_id(user_id)

        match = self._RESOURCES_USER_PATTERN.search(normalized)
        if match:
            scoped_user = self._sanitize_segment(match.group(1))
            if scoped_user and scoped_user != safe_user:
                logger.debug(
                    f"[OpenViking] blocked cross-user resources URI "
                    f"user={safe_user} target={scoped_user} uri={normalized}"
                )
                return True

        user_match = self._USER_PATH_PATTERN.match(normalized)
        if user_match:
            scoped = self._sanitize_segment(user_match.group(1))
            if scoped and scoped not in {"memories", safe_user}:
                logger.debug(
                    f"[OpenViking] blocked cross-user explicit URI "
                    f"user={safe_user} target={scoped} uri={normalized}"
                )
                return True

        return False

    def user_memories_uri(self, user_id: str) -> str:
        safe_user = normalize_user_id(user_id)
        return f"viking://user/{safe_user}/memories/"

    def read_abstract(

        self,
        uri: str,
        user_id: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> str:
        if not self.enabled:
            return ""
        if self._is_user_scope_guard_blocked(uri, user_id=user_id, api_key=api_key):
            return ""

        try:
            result = self._request(
                "GET",
                OpenVikingAPI.CONTENT_ABSTRACT,
                params={"uri": uri},
                allow_not_found=True,
                user_id=user_id,
                api_key=api_key,
            )
            return str(result or "").strip()
        except Exception as exc:
            if self._is_missing_path_error(exc):
                return ""
            logger.debug(f"[OpenViking] abstract failed for {uri}: {exc}")
            return ""

    def read_overview(
        self,
        uri: str,
        user_id: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> str:
        if not self.enabled:
            return ""
        if self._is_user_scope_guard_blocked(uri, user_id=user_id, api_key=api_key):
            return ""

        try:
            result = self._request(
                "GET",
                OpenVikingAPI.CONTENT_OVERVIEW,
                params={"uri": uri},
                allow_not_found=True,
                user_id=user_id,
                api_key=api_key,
            )
            return str(result or "").strip()
        except Exception as exc:
            if self._is_missing_path_error(exc):
                return ""
            logger.debug(f"[OpenViking] overview failed for {uri}: {exc}")
            return ""

    def read_user_memory_profile(self, user_id: str) -> str:
        if not self.enabled:
            return ""
        overview_root_uri = self.user_memories_uri(user_id)
        overview = self.read_overview(overview_root_uri, user_id=user_id).strip()
        if overview:
            logger.debug(
                f"[OpenViking] read_user_memory_profile user={user_id} "
                f"source=overview_api uri={overview_root_uri}"
            )
            return overview
        logger.debug(
            f"[OpenViking] read_user_memory_profile user={user_id} "
            f"source=empty uri={overview_root_uri}"
        )
        return ""

    def store_user_memory(self, user_id: str, session_id: str, text: str) -> Dict[str, Any]:
        if not self.enabled:
            return {
                "stored": False,
                "append_ok": False,
                "commit_ok": False,
                "extracted_count": 0,
                "warning": "openviking_disabled",
            }
        if not self.key_manager.ensure_user_identity(user_id):
            return {
                "stored": False,
                "append_ok": False,
                "commit_ok": False,
                "extracted_count": 0,
                "warning": "user_identity_not_ready",
            }

        message = (text or "").strip()
        if not message:
            return {
                "stored": False,
                "append_ok": False,
                "commit_ok": False,
                "extracted_count": 0,
                "warning": "empty_memory_text",
            }

        ov_session_id = self._explicit_memory_store_session_id(user_id, session_id=session_id, text=message)
        logger.debug(
            f"[OpenViking] memory_store_extract user={user_id} "
            f"business_session={session_id or 'default'} session={ov_session_id}"
        )
        try:
            self._request(
                "POST",
                OpenVikingAPI.session_messages(ov_session_id),
                json_body={
                    "role": "user",
                    "content": message,
                },
                user_id=user_id,
            )
            extracted = self._extract_memory_session(user_id=user_id, ov_session_id=ov_session_id)
            commit_ok = bool(extracted.get("commit_ok", False))
            extracted_count = int(extracted.get("extracted_count", 0) or 0)
            warning = str(extracted.get("warning", "") or "")
            return {
                "stored": commit_ok and extracted_count > 0,
                "append_ok": True,
                "commit_ok": commit_ok,
                "extracted_count": extracted_count,
                "warning": warning,
            }
        except Exception as exc:
            logger.debug(
                f"[OpenViking] store_user_memory failed user={user_id} "
                f"business_session={session_id or 'default'} session={ov_session_id}: {exc}"
            )
            return {
                "stored": False,
                "append_ok": False,
                "commit_ok": False,
                "extracted_count": 0,
                "warning": f"store_failed:{exc}",
            }
        finally:
            self._delete_session_best_effort(user_id=user_id, ov_session_id=ov_session_id)

    def append_long_term_session_records(
        self,
        *,
        user_id: str,
        session_id: str = "",
        user_text: str,
        assistant_text: str,
        used_contexts: Optional[list[str]] = None,
        used_skills: Optional[list[dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        if not self.enabled:
            return {
                "stored": False,
                "append_ok": False,
                "commit_ok": False,
                "extracted_count": 0,
                "warning": "openviking_disabled",
            }
        if not self.key_manager.ensure_user_identity(user_id):
            return {
                "stored": False,
                "append_ok": False,
                "commit_ok": False,
                "extracted_count": 0,
                "warning": "user_identity_not_ready",
            }

        query_text = str(user_text or "").strip()
        response_text = str(assistant_text or "").strip()
        context_uris = [str(item or "").strip() for item in (used_contexts or []) if str(item or "").strip()]
        skill_records = [item for item in (used_skills or []) if isinstance(item, dict)]
        if not query_text and not response_text and not context_uris and not skill_records:
            return {
                "stored": False,
                "append_ok": False,
                "commit_ok": False,
                "extracted_count": 0,
                "warning": "empty_session_records",
            }

        ov_session_id = self._memory_session_id(user_id, session_id=session_id)
        try:
            if query_text:
                user_parts = self._build_runtime_user_parts(query_text)
                self._request(
                    "POST",
                    OpenVikingAPI.session_messages(ov_session_id),
                    json_body={
                        "role": "user",
                        "parts": user_parts,
                    },
                    user_id=user_id,
                )
            assistant_parts = self._build_runtime_assistant_parts(
                response_text,
                user_id=user_id,
                used_contexts=context_uris,
                used_skills=skill_records,
            )
            if assistant_parts:
                self._request(
                    "POST",
                    OpenVikingAPI.session_messages(ov_session_id),
                    json_body={
                        "role": "assistant",
                        "parts": assistant_parts,
                    },
                    user_id=user_id,
                )

            self._record_runtime_usage(
                user_id=user_id,
                session_id=ov_session_id,
                used_contexts=context_uris,
                used_skills=skill_records,
            )
            state = self._mark_memory_session_pending(user_id, session_id=session_id)
            committed = self._commit_user_memory_session_if_due(user_id, session_id=session_id, state=state)
            commit_ok = bool(committed.get("commit_ok", False)) if isinstance(committed, dict) else bool(committed)
            extracted_count = int((committed or {}).get("extracted_count", 0) or 0)
            warning = str((committed or {}).get("warning", "") or "")
            if not state.get("commit_due"):
                warning = warning or "pending_commit"
            return {
                "stored": commit_ok and extracted_count > 0,
                "append_ok": True,
                "commit_ok": commit_ok,
                "extracted_count": extracted_count,
                "warning": warning,
            }
        except Exception as exc:
            logger.debug(
                f"[OpenViking] append_long_term_session_records failed user={user_id} "
                f"business_session={session_id or 'default'} session={ov_session_id}: {exc}"
            )
            return {
                "stored": False,
                "append_ok": False,
                "commit_ok": False,
                "extracted_count": 0,
                "warning": f"session_append_failed:{exc}",
            }

    def _memory_session_id(self, user_id: str, session_id: str = "") -> str:
        safe_user = normalize_user_id(user_id)
        safe_session = self._sanitize_segment(str(session_id or "").strip())[:64]
        if safe_session:
            return f"{self._MEMORY_SESSION_PREFIX}_{safe_user}_{safe_session}"
        return f"{self._MEMORY_SESSION_PREFIX}_{safe_user}"

    def _explicit_memory_store_session_id(self, user_id: str, *, session_id: str = "", text: str) -> str:
        base_session = self._sanitize_segment(str(session_id or "").strip())[:40] or "default"
        content_hash = hashlib.md5(str(text or "").encode("utf-8")).hexdigest()[:12]
        safe_user = normalize_user_id(user_id)
        return f"{self._MEMORY_SESSION_PREFIX}_{safe_user}_explicit_{base_session}_{content_hash}"

    @staticmethod
    def _build_runtime_user_parts(text: str) -> list[dict[str, Any]]:
        content = str(text or "").strip()
        if not content:
            return []
        return [{"type": "text", "text": content}]

    def _build_runtime_assistant_parts(
        self,
        text: str,
        *,
        user_id: str,
        used_contexts: Optional[list[str]] = None,
        used_skills: Optional[list[dict[str, Any]]] = None,
    ) -> list[dict[str, Any]]:
        parts: list[dict[str, Any]] = []
        content = str(text or "").strip()
        if content:
            parts.append({"type": "text", "text": content})

        seen_contexts = set()
        for uri in used_contexts or []:
            normalized_uri = str(uri or "").strip()
            if not normalized_uri or normalized_uri in seen_contexts:
                continue
            seen_contexts.add(normalized_uri)
            parts.append(
                {
                    "type": "context",
                    "uri": normalized_uri,
                    "context_type": self._context_part_type_for_uri(normalized_uri),
                    "abstract": self._safe_context_abstract(normalized_uri, user_id=user_id),
                }
            )

        for index, skill in enumerate(used_skills or [], start=1):
            tool_part = self._build_tool_part(skill, index=index)
            if tool_part:
                parts.append(tool_part)
        return parts

    @staticmethod
    def _context_part_type_for_uri(uri: str) -> str:
        normalized = str(uri or "").strip().lower()
        if "/skills/" in normalized or normalized.startswith("viking://skill/"):
            return "skill"
        if "/resources/" in normalized or normalized.startswith("viking://resources/"):
            return "resource"
        return "memory"

    def _safe_context_abstract(self, uri: str, *, user_id: str) -> str:
        normalized_uri = str(uri or "").strip()
        if not normalized_uri.startswith("viking://"):
            return ""
        # OpenViking content/abstract is directory-oriented in current deployment.
        # Calling abstract on file URIs (e.g. *.md, .overview.md) returns 500
        # "is not a directory", which amplifies retries/noise in memory writes.
        if not normalized_uri.endswith("/"):
            return ""
        try:
            return self.read_abstract(normalized_uri, user_id=user_id).strip()[:500]
        except Exception:
            return ""

    def _build_tool_part(self, skill: dict[str, Any], *, index: int) -> Optional[dict[str, Any]]:
        if not isinstance(skill, dict):
            return None

        tool_name = str(skill.get("tool_name", "") or "").strip()
        agent_name = str(skill.get("agent_name", "") or "").strip()
        tool_uri = str(skill.get("tool_uri", "") or skill.get("uri", "") or "").strip()
        skill_uri = str(skill.get("skill_uri", "") or "").strip()
        tool_input = skill.get("input", {})
        if not isinstance(tool_input, dict):
            tool_input = {"value": tool_input}
        tool_output = str(skill.get("output", "") or "").strip()
        success = bool(skill.get("success", True))
        round_index = int(skill.get("round_index", 0) or 0)

        if not (tool_name or tool_uri or skill_uri or tool_output or tool_input):
            return None

        tool_id_seed = f"{agent_name}:{tool_name}:{round_index}:{index}"
        tool_id = f"tool_{hashlib.md5(tool_id_seed.encode('utf-8')).hexdigest()[:12]}"
        return {
            "type": "tool",
            "tool_id": tool_id,
            "tool_name": tool_name,
            "tool_uri": tool_uri,
            "skill_uri": skill_uri,
            "tool_input": tool_input,
            "tool_output": tool_output[:2000],
            "tool_status": "completed" if success else "failed",
        }

    def _record_runtime_usage(
        self,
        *,
        user_id: str,
        session_id: str,
        used_contexts: Optional[list[str]] = None,
        used_skills: Optional[list[dict[str, Any]]] = None,
    ) -> bool:
        contexts = [str(item or "").strip() for item in (used_contexts or []) if str(item or "").strip()]
        skills = [item for item in (used_skills or []) if isinstance(item, dict)]
        if not contexts and not skills:
            return True
        try:
            if contexts:
                self._request(
                    "POST",
                    OpenVikingAPI.session_used(session_id),
                    json_body={
                        "contexts": contexts,
                    },
                    user_id=user_id,
                )
            # Skill usage is already embedded in assistant parts as tool blocks.
            # Skip duplicated /used skill writes to reduce request fan-out and write noise.
            return True
        except Exception as exc:
            logger.debug(f"[OpenViking] used endpoint unavailable user={user_id} session={session_id}: {exc}")
            return False

    def commit_user_memory_session(self, user_id: str, session_id: str = "", force: bool = False) -> Dict[str, Any]:
        if not self.enabled:
            return {"commit_ok": False, "extracted_count": 0, "warning": "openviking_disabled"}

        safe_user = normalize_user_id(user_id)
        session_key = self._memory_session_id(user_id, session_id=session_id)
        timer = self._memory_session_timers.pop(session_key, None)
        if timer is not None and timer.is_alive():
            timer.cancel()
        state = self._memory_session_state.get(session_key)
        pending_count = int(float((state or {}).get("pending_count", 0.0) or 0.0))
        if not force and pending_count <= 0:
            return {"commit_ok": True, "extracted_count": 0, "warning": "no_pending_messages"}

        ov_session_id = self._memory_session_id(user_id, session_id=session_id)
        try:
            result = self._request(
                "POST",
                OpenVikingAPI.session_commit(ov_session_id),
                params={"wait": "false"},
                json_body={},
                user_id=user_id,
            )
            if isinstance(result, dict) and str(result.get("status", "")).strip().lower() == "accepted":
                task_id = str(result.get("task_id", "") or "").strip()
                logger.debug(
                    f"[OpenViking] accepted async commit user={safe_user} session={ov_session_id} "
                    f"task_id={task_id or 'missing'}"
                )
                self._memory_session_state[session_key] = {
                    "pending_count": 0.0,
                    "last_commit_at": time.time(),
                }
                return {
                    "commit_ok": True,
                    "extracted_count": 0,
                    "warning": "commit_processing",
                }
            extracted_count = int((result or {}).get("memories_extracted", 0) or 0)
            logger.info(
                f"[OpenViking] committed memory session user={safe_user} "
                f"session={ov_session_id} memories_extracted="
                f"{extracted_count}"
            )
            self._memory_session_state[session_key] = {
                "pending_count": 0.0,
                "last_commit_at": time.time(),
            }
            warning = ""
            if extracted_count <= 0:
                warning = "openviking_commit_ok_but_no_memory_extracted"
            return {
                "commit_ok": True,
                "extracted_count": extracted_count,
                "warning": warning,
            }
        except Exception as exc:
            error_text = str(exc or "")
            if "already has a commit in progress" in error_text.lower():
                logger.debug(
                    f"[OpenViking] commit already in progress user={safe_user} session={ov_session_id}"
                )
                return {
                    "commit_ok": True,
                    "extracted_count": 0,
                    "warning": "commit_processing",
                }
            logger.debug(
                f"[OpenViking] commit memory session failed user={safe_user} "
                f"session={ov_session_id}: {exc}"
            )
            return {
                "commit_ok": False,
                "extracted_count": 0,
                "warning": f"commit_failed:{exc}",
            }

    def _mark_memory_session_pending(self, user_id: str, session_id: str = "") -> Dict[str, float]:
        session_key = self._memory_session_id(user_id, session_id=session_id)
        now = time.time()
        state = dict(self._memory_session_state.get(session_key, {}))
        pending_count = int(float(state.get("pending_count", 0.0) or 0.0)) + 1
        first_pending_at = float(state.get("first_pending_at", now) or now)
        if pending_count <= 1:
            first_pending_at = now
        updated = {
            "pending_count": float(pending_count),
            "first_pending_at": first_pending_at,
            "last_append_at": now,
            "last_commit_at": float(state.get("last_commit_at", 0.0) or 0.0),
        }
        commit_due = pending_count >= self.session_commit_every_n
        max_age_seconds = max(float(self.session_commit_max_age_seconds), 0.0)
        if not commit_due and max_age_seconds > 0 and now - first_pending_at >= max_age_seconds:
            commit_due = True
        updated["commit_due"] = 1.0 if commit_due else 0.0
        self._memory_session_state[session_key] = updated
        if not commit_due:
            self._schedule_idle_commit(user_id, session_id=session_id, delay_seconds=self.idle_commit_seconds)
        return updated

    def _commit_user_memory_session_if_due(
        self,
        user_id: str,
        *,
        session_id: str = "",
        state: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        session_key = self._memory_session_id(user_id, session_id=session_id)
        session_state = state or self._memory_session_state.get(session_key, {})
        if not bool(int(float((session_state or {}).get("commit_due", 0.0) or 0.0))):
            return {
                "commit_ok": False,
                "extracted_count": 0,
                "warning": "pending_commit",
            }
        return self.commit_user_memory_session(user_id, session_id=session_id, force=True)

    def _schedule_idle_commit(self, user_id: str, *, session_id: str = "", delay_seconds: int) -> None:
        if not self.idle_commit_enabled:
            return

        safe_user = normalize_user_id(user_id)
        session_key = self._memory_session_id(user_id, session_id=session_id)
        existing = self._memory_session_timers.pop(session_key, None)
        if existing is not None and existing.is_alive():
            existing.cancel()

        def _commit_on_idle() -> None:
            try:
                self.commit_user_memory_session(user_id, session_id=session_id, force=False)
            except Exception as exc:
                logger.debug(
                    f"[OpenViking] idle commit failed user={safe_user} "
                    f"business_session={session_id or 'default'}: {exc}"
                )

        timer = threading.Timer(max(delay_seconds, 1), _commit_on_idle)
        timer.daemon = True
        self._memory_session_timers[session_key] = timer
        timer.start()

    def _extract_memory_session(self, *, user_id: str, ov_session_id: str) -> Dict[str, Any]:
        try:
            extracted = self._request(
                "POST",
                OpenVikingAPI.session_extract(ov_session_id),
                json_body={},
                user_id=user_id,
            )
            extracted_rows = extracted if isinstance(extracted, list) else []
            return {
                "commit_ok": True,
                "extracted_count": len(extracted_rows),
                "warning": "" if extracted_rows else "openviking_commit_ok_but_no_memory_extracted",
            }
        except Exception as exc:
            logger.debug(f"[OpenViking] extract session failed user={user_id} session={ov_session_id}: {exc}")
            return {
                "commit_ok": False,
                "extracted_count": 0,
                "warning": f"extract_failed:{exc}",
            }

    def _delete_session_best_effort(self, *, user_id: str, ov_session_id: str) -> None:
        try:
            self._request(
                "DELETE",
                OpenVikingAPI.session_root(ov_session_id),
                allow_not_found=True,
                user_id=user_id,
            )
        except Exception as exc:
            logger.debug(f"[OpenViking] delete session failed user={user_id} session={ov_session_id}: {exc}")

    def recall_matches_for_target_uri(
        self,
        *,
        user_id: str,
        query: str,
        target_uri: str,
        limit: Optional[int] = None,
        source_label: str = "target",
        api_key: Optional[str] = None,
    ) -> dict[str, Any]:
        if not self.enabled:
            return {"rows": [], "fallback_path": "disabled"}
        q = str(query or "").strip()
        if not q:
            return {"rows": [], "fallback_path": "empty_query"}
        normalized_target_uri = str(target_uri or "").strip()
        if not normalized_target_uri.startswith("viking://"):
            return {"rows": [], "fallback_path": "invalid_target_uri"}
        if self._is_user_scope_guard_blocked(normalized_target_uri, user_id=user_id, api_key=api_key):
            return {"rows": [], "fallback_path": "guard_blocked"}

        effective_limit = int(limit or self.search_limit or 10)
        effective_limit = max(min(effective_limit, 50), 1)
        safe_label = self._sanitize_segment(source_label) or "target"

        try:
            result = self._request(
                "POST",
                OpenVikingAPI.SEARCH_FIND,
                json_body={
                    "query": q,
                    "target_uri": normalized_target_uri,
                    "limit": effective_limit,
                    "score_threshold": 0.0,
                },
                user_id=user_id,
                api_key=api_key,
                timeout_seconds=self.recall_timeout_seconds,
            )
        except Exception as exc:
            logger.debug(
                f"[OpenViking] recall find failed user={user_id} target={normalized_target_uri} "
                f"timeout={self.recall_timeout_seconds}s err={exc}"
            )
            return {"rows": [], "fallback_path": f"find_{safe_label}_error"}

        rows = self._extract_recall_rows(result)
        if not rows:
            logger.info(
                f"[OpenViking] recall_find no hits user={user_id} "
                f"source={safe_label} target={normalized_target_uri} query={q[:40]!r}"
            )
            return {"rows": [], "fallback_path": f"find_{safe_label}_no_hits"}

        dedup: dict[tuple[str, str], dict] = {}
        for item in rows:
            uri = str(item.get("uri", "")).strip()
            abstract = str(item.get("abstract", "")).strip()
            key = (uri, abstract)
            existing = dedup.get(key)
            if existing is None or float(item.get("score", 0.0) or 0.0) > float(existing.get("score", 0.0) or 0.0):
                dedup[key] = item

        merged_rows = list(dedup.values())
        merged_rows.sort(
            key=lambda item: (
                -float(item.get("score", 0.0) or 0.0),
                int(item.get("level", 2) or 2),
                str(item.get("uri", "") or ""),
            )
        )
        uri_preview = [
            str(item.get("uri", "")).strip()
            for item in merged_rows[:10]
            if str(item.get("uri", "")).strip()
        ]

        logger.debug(
            f"[OpenViking] recall_find hits={len(merged_rows)} user={user_id} "
            f"source={safe_label} target={normalized_target_uri} "
            f"hit_uris={uri_preview}"
        )
        return {
            "rows": merged_rows[:effective_limit],
            "fallback_path": f"find_{safe_label}",
        }

    @staticmethod
    def _extract_recall_rows(result: Any) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        result_obj = result if isinstance(result, dict) else {}
        for key in ("memories", "resources", "skills"):
            for item in (result_obj.get(key, []) or []):
                abstract = str((item or {}).get("abstract", "") or "")
                uri = str((item or {}).get("uri", "") or "")
                if abstract:
                    rows.append(
                        {
                            "uri": uri,
                            "category": str((item or {}).get("category", "") or key[:-1]),
                            "context_type": str((item or {}).get("context_type", "") or key[:-1]),
                            "abstract": abstract,
                            "overview": str((item or {}).get("overview", "") or ""),
                            "score": float((item or {}).get("score", 0.0) or 0.0),
                            "level": int((item or {}).get("level", 2) or 2),
                            "is_leaf": bool((item or {}).get("is_leaf", False)),
                            "match_reason": str((item or {}).get("match_reason", "") or ""),
                        }
                    )
        return rows


