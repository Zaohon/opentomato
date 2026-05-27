import os
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger
from app.core.memory.memory_policy import (
    MemoryPolicy,
    format_injection_block,
    pick_memories_for_injection,
    post_process_memories,
)
from app.core.memory.provider import OpenVikingContentProvider

logger = get_logger("app.memory.service")


class MemoryService:
    """
    Unified memory service.

    Session context is owned by the frontend and passed to the backend via chat history.
    OpenViking is the source of truth for long-term memory and derived memory summary.
    """

    def __init__(
        self,
        openviking_provider: Optional[OpenVikingContentProvider] = None,
    ):
        self.openviking = openviking_provider or OpenVikingContentProvider()
        self.policy = MemoryPolicy()
        self.enabled = bool(self.openviking and self.openviking.enabled)
        self.expected_enabled = bool(getattr(self.openviking, "expected_enabled", False))
        self.recall_score_threshold = max(float(os.getenv("MEMORY_RECALL_SCORE_THRESHOLD", "0.01") or "0.01"), 0.0)
        self.recall_post_limit = max(int(os.getenv("MEMORY_RECALL_POST_LIMIT", "20") or "20"), 1)
        self.recall_pick_limit = max(int(os.getenv("MEMORY_RECALL_PICK_LIMIT", "6") or "6"), 1)
        self.recall_resource_targets = self._parse_resource_targets()
        self.recall_resource_search_limit = max(
            min(
                int(os.getenv("MEMORY_RECALL_RESOURCE_SEARCH_LIMIT", str(self.openviking.search_limit)) or self.openviking.search_limit),
                50,
            ),
            1,
        )
        if not self.enabled:
            logger.warning("[Memory] OpenViking long-term memory is disabled.")

    @staticmethod
    def _parse_resource_targets() -> List[str]:
        raw = str(os.getenv("MEMORY_RECALL_RESOURCE_URIS", "") or "").strip()
        if not raw:
            return []
        parts = raw.replace(";", ",").split(",")
        targets: List[str] = []
        seen = set()
        for item in parts:
            uri = str(item or "").strip()
            if not uri:
                continue
            if not uri.startswith("viking://"):
                continue
            if uri in seen:
                continue
            seen.add(uri)
            targets.append(uri)
        return targets

    def precreate_users(self, logger_obj=None, raw_users: Optional[str] = None) -> dict:
        log = logger_obj or logger
        if not self.enabled:
            log.info("openviking precreate enabled=false")
            return {"enabled": False, "requested": 0, "success": 0, "failed": 0}
        raw = (raw_users if raw_users is not None else os.getenv("OPENVIKING_PRECREATE_USERS", "") or "").strip()
        users = [u.strip() for u in raw.split(",") if u.strip()] if raw else []
        if not users:
            return {"enabled": True, "requested": 0, "success": 0, "failed": 0, "status": "skipped"}
        result = self.openviking.key_manager.precreate_users(users)
        success_count = len(result.get("success", []) or [])
        failed_count = len(result.get("failed", {}) or {})
        log.info(
            "openviking precreate status=done requested=%s success=%d failed=%d",
            result.get("requested", 0),
            success_count,
            failed_count,
        )
        if failed_count:
            log.warning("openviking precreate failures=%s", result.get("failed", {}))
        return {
            "enabled": True,
            "requested": int(result.get("requested", 0) or 0),
            "success": success_count,
            "failed": failed_count,
            "status": "done",
        }

    def store_explicit_fact(
        self,
        *,
        user_id: str,
        session_id: str = "",
        text: str,
    ) -> Dict[str, Any]:
        normalized_text = str(text or "").strip()
        if not normalized_text:
            return {"stored": False, "warning": "empty_memory_text"}
        result: Dict[str, Any] = {
            "stored": False,
            "append_ok": False,
            "commit_ok": False,
            "extracted_count": 0,
            "warning": "",
        }
        if not self.enabled:
            return result

        logger.info(f"[Memory] Storing long-term memory user={user_id}")
        store_result = self.openviking.store_user_memory(
            user_id=user_id,
            session_id=session_id,
            text=normalized_text,
        )
        if isinstance(store_result, dict):
            result["append_ok"] = bool(store_result.get("append_ok", False))
            result["commit_ok"] = bool(store_result.get("commit_ok", False))
            result["extracted_count"] = int(store_result.get("extracted_count", 0) or 0)
            result["warning"] = str(store_result.get("warning", "") or "")
            result["stored"] = bool(store_result.get("stored", False))
        else:
            result["stored"] = bool(store_result)

        if result["append_ok"] and not result["commit_ok"]:
            logger.debug(
                f"[Memory] Skipping post-store refresh until session commit user={user_id} "
                f"warning={result['warning'] or 'pending_commit'}"
            )

        logger.info(
            f"[Memory] long_term_store_result user={user_id} "
            f"stored={'true' if result['stored'] else 'false'} "
            f"append_ok={'true' if result['append_ok'] else 'false'} "
            f"commit_ok={'true' if result['commit_ok'] else 'false'} "
            f"extracted={result['extracted_count']} "
            f"warning={result['warning'] or 'none'}"
        )
        return result

    def append_session_records(
        self,
        *,
        user_id: str,
        session_id: str = "",
        turn_record: Dict[str, Any],
    ) -> Dict[str, Any]:
        payload = turn_record if isinstance(turn_record, dict) else {}
        turn = payload.get("turn", {}) if isinstance(payload.get("turn", {}), dict) else {}
        usage = payload.get("usage", {}) if isinstance(payload.get("usage", {}), dict) else {}
        if not any(
            [
                str(turn.get("user_text", "") or "").strip(),
                str(turn.get("assistant_text", "") or "").strip(),
                usage.get("contexts", []),
                usage.get("skills", []),
            ]
        ):
            return {"append_ok": False, "warning": "empty_session_records"}

        return self.openviking.append_long_term_session_records(
            user_id=user_id,
            session_id=session_id,
            user_text=str(turn.get("user_text", "") or ""),
            assistant_text=str(turn.get("assistant_text", "") or ""),
            used_contexts=usage.get("contexts", []),
            used_skills=usage.get("skills", []),
        )

    def recall_bundle(
        self,
        *,
        query: str,
        user_id: str,
        session_id: str = "",
        query_text_for_rank: str = "",
        caller: str = "unknown",
    ) -> Dict[str, Any]:
        q = str(query or "").strip()
        if not self.enabled or not q:
            return {
                "query": q,
                "hits": 0,
                "picked": 0,
                "fallback_path": "disabled_or_empty",
                "matches": [],
                "picked_items": [],
                "rendered": "",
            }
        fallback_path = "find_user_only"
        matches: List[Dict[str, Any]] = []
        user_hits = 0
        resource_hits = 0
        try:
            user_meta = self.openviking.recall_matches_for_target_uri(
                user_id=user_id,
                query=q,
                target_uri=self.openviking.user_memories_uri(user_id),
                source_label="user_only",
            )
            if isinstance(user_meta, dict):
                user_rows = list(user_meta.get("rows", []) or [])
                for row in user_rows:
                    if isinstance(row, dict):
                        row.setdefault("recall_source", "user_memory")
                matches.extend(user_rows)
                user_hits = len(user_rows)
                fallback_path = str(user_meta.get("fallback_path", "") or fallback_path)
        except Exception as exc:
            logger.warning(f"[Memory] recall_bundle failed user={user_id}: {exc}")
            matches = []
            fallback_path = "error"

        resource_fallbacks: List[str] = []
        resource_api_key = self.openviking.resolve_resource_recall_api_key()
        for target_uri in self.recall_resource_targets:
            try:
                resource_meta = self.openviking.recall_matches_for_target_uri(
                    user_id=user_id,
                    query=q,
                    target_uri=target_uri,
                    limit=self.recall_resource_search_limit,
                    source_label="resource",
                    api_key=resource_api_key or None,
                )
                if not isinstance(resource_meta, dict):
                    continue
                rows = list(resource_meta.get("rows", []) or [])
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    row.setdefault("recall_source", "resource")
                    row.setdefault("target_uri", target_uri)
                matches.extend(rows)
                resource_hits += len(rows)
                fp = str(resource_meta.get("fallback_path", "") or "").strip()
                if fp:
                    resource_fallbacks.append(fp)
            except Exception as exc:
                logger.warning(
                    f"[Memory] recall_bundle resource_find failed user={user_id} "
                    f"target={target_uri}: {exc}"
                )
                resource_fallbacks.append("find_resource_error")

        if self.recall_resource_targets:
            fallback_path = f"{fallback_path}|resource:{'|'.join(resource_fallbacks) if resource_fallbacks else 'none'}"

        leaf_processed = post_process_memories(
            matches,
            limit=self.recall_post_limit,
            score_threshold=self.recall_score_threshold,
            leaf_only=True,
        )
        processed = leaf_processed
        ranking_path = "leaf"
        if not processed:
            processed = post_process_memories(
                matches,
                limit=self.recall_post_limit,
                score_threshold=self.recall_score_threshold,
                leaf_only=False,
            )
            ranking_path = "fallback_non_leaf"

        rank_query = str(query_text_for_rank or q).strip()
        picked = pick_memories_for_injection(
            processed,
            query_text=rank_query,
            limit=self.recall_pick_limit,
        )
        rendered = format_injection_block(picked) if picked else ""
        log_line = (
            f"[MemoryRecall] caller={caller} user={user_id} "
            f"query={q!r} hits={len(matches)} picked={len(picked)} "
            f"fallback_path={fallback_path}/{ranking_path}"
        )
        logger.info(log_line)
        return {
            "query": q,
            "hits": len(matches),
            "hits_user_memory": user_hits,
            "hits_resource": resource_hits,
            "picked": len(picked),
            "fallback_path": f"{fallback_path}/{ranking_path}",
            "matches": matches,
            "picked_items": picked,
            "rendered": rendered,
        }

    def load_memory_summary(self, username: str) -> str:
        logger.debug(f"[Memory] Loading memory summary from OpenViking user={username}")
        content = self.openviking.read_user_memory_profile(username)
        return content

    def close(self) -> None:
        try:
            self.openviking.close()
        except Exception:
            pass
