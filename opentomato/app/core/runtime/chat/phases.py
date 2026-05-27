from __future__ import annotations

from enum import Enum


class RuntimePhase(str, Enum):
    LOAD_USER_SUMMARY = "load_user_summary"
    LOAD_CHAT_HISTORY = "load_chat_history"
    FIND_MEMORY = "find_memory"
    CAPTURE_MEMORY = "capture_memory"
    DISPATCH_AGENT = "dispatch_agent"
    FINAL_ANSWER = "final_answer"
    SAVE_MEMORY = "save_memory"
