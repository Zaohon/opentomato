from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from app.core.logging import get_logger
from app.core.memory.memory_policy import format_injection_block
from app.core.memory.service import MemoryService
from app.core.text import merge_sections

if TYPE_CHECKING:
    from app.core.runtime.chat.chat_runtime import ChatRuntime

logger = get_logger("app.runtime.memory_hook")


class MemoryFindHook:
    order = 130

    def __init__(self, memory_service: Optional[MemoryService]) -> None:
        self.memory_service = memory_service

    def run(self, state: "ChatRuntime") -> None:
        if self.memory_service is None or not bool(getattr(self.memory_service, "enabled", False)):
            return
        query = str(state.query or "").strip()
        if not query:
            return

        bundle = self.memory_service.recall_bundle(
            query=query,
            user_id=state.user_id,
            session_id=state.session_id,
            query_text_for_rank=query,
            caller="phase_find_memory",
        )
        picked_items = list(bundle.get("picked_items", []) or [])
        if picked_items:
            section = build_recall_prompt_injection(
                reason="phase_find_memory",
                query=query,
                picked_items=picked_items,
            )
            state.ctx.rag_context = merge_sections(state.ctx.rag_context, section)
            picked_briefs: List[Dict[str, str]] = []
            for item in picked_items:
                if not isinstance(item, dict):
                    continue
                uri = str(item.get("uri", "") or "").strip()
                category = str(item.get("category", "") or "").strip()
                text = str(
                    item.get("abstract", "")
                    or item.get("overview", "")
                    or item.get("content", "")
                    or ""
                ).strip()
                if len(text) > 160:
                    text = text[:157] + "..."
                picked_briefs.append(
                    {
                        "uri": uri,
                        "category": category,
                        "text": text,
                    }
                )
        used_contexts: List[str] = []
        seen = set()
        for item in picked_items:
            if not isinstance(item, dict):
                continue
            uri = str(item.get("uri", "") or "").strip()
            if not uri or uri in seen:
                continue
            seen.add(uri)
            used_contexts.append(uri)
        if used_contexts:
            existing = list(state.artifacts.get("used_contexts", []) or [])
            merged: List[str] = []
            merged_seen = set()
            for uri in existing + used_contexts:
                text = str(uri or "").strip()
                if not text or text in merged_seen:
                    continue
                merged_seen.add(text)
                merged.append(text)
            state.artifacts["used_contexts"] = merged

        # Recall already completed in phase hook; skip duplicate auto-recall inside agent plugin.
        state.ctx.disable_memory_recall = True



def build_recall_prompt_injection(
    *,
    reason: str,
    query: str,
    picked_items: List[Dict[str, Any]],
) -> str:
    if picked_items:
        injection_block = format_injection_block(picked_items)
        detailed_lines = []
        for item in picked_items:
            category = str(item.get("category", "") or "memory")
            abstract = str(item.get("abstract", "") or item.get("overview", "") or item.get("uri", "")).strip()
            detailed_lines.append(f"- [{category}] {abstract}")
        return (
            "[SYSTEM AUTO RECALL]\n"
            f"reason: {reason}\n"
            f"query: {query}\n"
            f"{injection_block}\n"
            + "\n".join(detailed_lines)
        )
    return (
        "[SYSTEM AUTO RECALL]\n"
        f"reason: {reason}\n"
        f"query: {query}\n"
        "No relevant long-term memories found."
    )
