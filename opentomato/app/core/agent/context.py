from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ConversationContext:
    """Structured context passed from orchestration layer to every agent."""

    request_id: str = ""
    session_id: str = ""
    user_id: str = "default_user"
    query: str = ""
    user_language: str = "zh-CN"
    chat_history: List[Dict[str, str]] = field(default_factory=list)

    # Soul personality context (specifies unified agent personality)
    soul: str = "default"

    # Memory context (loaded by orchestration layer, consumed by agents)
    memory_summary_md: str = ""
    rag_context: str = ""
    current_time_local: str = ""
    current_time_iso: str = ""
    current_timezone: str = "Asia/Shanghai"
    current_weekday_local: str = ""

    # Control flags (set by orchestration for fast-paths)
    disable_memory_recall: bool = False
    disable_memory_store: bool = False
    disable_support_tools: bool = False

    @property
    def has_memory_summary(self) -> bool:
        return bool(self.memory_summary_md and self.memory_summary_md.strip())

    @property
    def has_rag(self) -> bool:
        return bool(self.rag_context and self.rag_context.strip())

    @property
    def language_policy_prompt_section(self) -> str:
        lang = str(self.user_language or "").strip() or "same_as_user"
        return (
            "\n\n[LANGUAGE POLICY]:\n"
            f"- User preferred language: {lang}\n"
            "- Always respond in the same language as the user's latest message.\n"
            "- Keep named entities unchanged.\n"
            "- When generating tool text arguments (such as memory recall query), "
            "use the user's language unless a tool explicitly requires another format.\n"
        )

    @property
    def current_time_prompt_section(self) -> str:
        local = str(self.current_time_local or "").strip()
        iso_text = str(self.current_time_iso or "").strip()
        tz = str(self.current_timezone or "").strip() or "Asia/Shanghai"
        weekday = str(self.current_weekday_local or "").strip()
        if not local and not iso_text:
            return ""
        lines = ["\n\n[CURRENT TIME - SERVER INJECTED]:", f"- Timezone: {tz}"]
        if local:
            lines.append(f"- Local datetime: {local}")
        if weekday:
            lines.append(f"- Local weekday: {weekday}")
        if iso_text:
            lines.append(f"- ISO datetime: {iso_text}")
        lines.append("- For time/date questions, use this timestamp and weekday as the source of truth.")
        lines.append("- Do not infer weekday from memory; trust the server-injected weekday.")
        return "\n".join(lines) + "\n"

    @property
    def memory_summary_prompt_section(self) -> str:
        if not self.has_memory_summary:
            return ""
        return (
            "\n\n[HOUSEHOLD LONG-TERM MEMORY SUMMARY]:\n"
            "Stable preferences, assets, and constraints derived from OpenViking. "
            "This is not real-time telemetry and must not be treated as final control evidence.\n"
            f"{self.memory_summary_md}\n"
        )

    @property
    def rag_prompt_section(self) -> str:
        if not self.has_rag:
            return ""
        return (
            "\n\n[Long-Term Memory (historical context from past conversations - "
            "NOT real-time data. For current battery SOC, power, device status, "
            "or any live telemetry, you MUST call the appropriate real-time tool)]:\n"
            f"{self.rag_context}\n"
        )

