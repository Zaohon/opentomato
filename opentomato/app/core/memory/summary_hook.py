from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Optional

from app.core.logging import get_logger
from app.core.memory.service import MemoryService

if TYPE_CHECKING:
    from app.core.runtime.chat.chat_runtime import ChatRuntime

logger = get_logger("app.runtime.memory_summary")


class MemorySummaryLoadHook:
    order = 100

    def __init__(self, memory_service: Optional[MemoryService]) -> None:
        self.memory_service = memory_service
        self.memory_summary_max_chars = max(int(os.getenv("MEMORY_SUMMARY_MAX_CHARS", "4500") or "4500"), 600)

    def run(self, state: "ChatRuntime") -> None:
        if state.memory_summary_md or self.memory_service is None:
            return
        try:
            raw_summary = self.memory_service.load_memory_summary(state.user_id) or ""
            state.memory_summary_md = self._build_injection_memory_summary(raw_summary)
        except Exception as exc:
            state.artifacts["memory_summary_load_failed"] = str(exc)
            logger.warning("memory_summary_load_failed user=%s error=%s", state.user_id, exc)

    @staticmethod
    def _normalize_summary_line(line: str) -> str:
        text = str(line or "").strip()
        if not text:
            return ""
        text = re.sub(r"^[#>\-\*\s]+", "", text)
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        return " ".join(text.split()).strip()

    def _truncate_summary(self, text: str) -> str:
        normalized = str(text or "").strip()
        if len(normalized) <= self.memory_summary_max_chars:
            return normalized
        return normalized[: self.memory_summary_max_chars].rstrip() + " ..."

    def _build_injection_memory_summary(self, raw_content: str) -> str:
        raw = str(raw_content or "").strip()
        if not raw:
            return ""

        lines = []
        for item in raw.splitlines():
            normalized = self._normalize_summary_line(item)
            if normalized:
                lines.append(normalized)
        if not lines:
            return self._truncate_summary(raw)

        fields = {}
        interests = []

        def contains_any(text: str, keywords: tuple[str, ...]) -> bool:
            lowered = text.lower()
            return any(key in lowered for key in keywords)

        for line in lines:
            if "identity" not in fields and contains_any(
                line,
                (
                    "real name",
                    "username",
                    "nickname",
                    "full name",
                    "user_",
                    "\u7528\u6237",
                    "\u59d3\u540d",
                    "\u7528\u6237\u540d",
                    "\u6635\u79f0",
                ),
            ):
                fields["identity"] = line
                continue

            if "residence" not in fields and contains_any(
                line,
                (
                    "residence",
                    "location",
                    "lives in",
                    "\u4f4f\u5728",
                    "\u5c45\u4f4f",
                    "\u6240\u5728\u5730",
                    "\u4e0a\u6d77",
                ),
            ):
                fields["residence"] = line
                continue

            if "household" not in fields and contains_any(
                line,
                (
                    "house",
                    "home",
                    "square-meter",
                    "square meter",
                    "\u5e73\u65b9\u7c73",
                    "\u623f\u5b50",
                    "\u5bb6\u5ead",
                ),
            ):
                fields["household"] = line
                continue

            if "pets" not in fields and contains_any(
                line,
                ("pets", "cat", "dog", "\u732b", "\u72d7"),
            ):
                fields["pets"] = line
                continue

            if len(interests) < 2 and contains_any(
                line,
                (
                    "interest",
                    "hobby",
                    "preference",
                    "energy management",
                    "cooking",
                    "\u5174\u8da3",
                    "\u504f\u597d",
                    "\u559c\u6b22",
                    "\u70f9\u996a",
                    "\u7528\u80fd",
                    "\u8282\u80fd",
                ),
            ):
                interests.append(line)

        if not fields and not interests:
            return self._truncate_summary(raw)

        compact_lines = ["# memory_profile"]
        order = (
            ("identity", "identity"),
            ("residence", "residence"),
            ("household", "household"),
            ("pets", "pets"),
        )
        for key, label in order:
            value = str(fields.get(key, "")).strip()
            if value:
                compact_lines.append(f"- {label}: {value}")
        if interests:
            compact_lines.append(f"- preferences: {'; '.join(interests)}")

        compact_lines.append("- note: derived from OpenViking L1 overview for prompt injection.")
        compact = "\n".join(compact_lines).strip()
        return self._truncate_summary(compact)

