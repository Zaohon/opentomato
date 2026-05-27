import importlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import unicodedata
from zoneinfo import ZoneInfo

from openai import OpenAI

from app.core.agent.base import BaseAgent
from app.core.agent.context import ConversationContext
from app.core.config.fls_agent import AgentSpec, get_skills_dir
from app.core.logging import get_logger
from app.core.memory.service import MemoryService
from app.core.tools_handler.registry import resolve_module

logger = get_logger("app.agent.engine")


class AgentEngine(BaseAgent):
    """Generic agent runtime driven by a startup-loaded AgentSpec."""

    def __init__(
        self,
        spec: AgentSpec,
        client: OpenAI,
        tools_handler: Any = None,
        memory_service: Optional[MemoryService] = None,
        **kwargs,
    ):
        model = kwargs.get("model") or spec.default_model or "qwen-plus"
        super().__init__(client, model)

        self.spec = spec
        self.agent_dir = Path(spec.agent_dir)
        self.name = spec.definition
        self.system_prompt = self._load_persona_short()
        self.tools_handler = tools_handler
        self.memory_service = memory_service
        self.skill_names = list(spec.skills)
        self.skill_blocks = self._load_skill_texts(self.skill_names)
        self.tools = self._bind_tools(spec.tools)
        self.allowed_handoffs = [
            item.strip()
            for item in (kwargs.get("allowed_handoffs") or spec.allowed_handoff or [])
            if isinstance(item, str) and item.strip()
        ]
        self.first_tool_choice = str(
            kwargs.get("first_tool_choice")
            or spec.execution.initial_tool_choice
            or "auto"
        )
        self.response_mode = str(
            kwargs.get("response_mode")
            or spec.execution.response_mode
            or "normal"
        ).strip().lower()
        self.default_handoff = str(
            kwargs.get("default_handoff")
            or spec.execution.default_handoff
            or "support_agent"
        ).strip()

    def _load_persona_short(self) -> str:
        persona_path = self.agent_dir / "agent.md"
        if not persona_path.exists():
            return "You are a helpful assistant."
        return self._normalize_prompt_text(persona_path.read_text(encoding="utf-8"))

    def _load_skill_texts(self, skill_names: List[str]) -> List[str]:
        """Load skill content from disk and format into blocks.

        Supports two layouts:
        - app/skills/<name>/skill.md (preferred)
        - app/skills/<name>.md (backward compatible)
        """
        skills_dir = get_skills_dir()
        blocks: List[str] = []
        for skill_name in skill_names:
            content = self._read_skill_content(skills_dir, skill_name)
            if content:
                blocks.append(f"[SKILL: {skill_name}]\n{self._normalize_prompt_text(content)}")
        return blocks

    @staticmethod
    def _normalize_prompt_text(text: str) -> str:
        """
        Normalize prompt text before sending to model to avoid hidden formatting drift.
        - strip UTF-8 BOM
        - normalize unicode to NFKC
        - unify newlines to LF
        - trim trailing spaces per line
        """
        raw = str(text or "")
        raw = raw.lstrip("\ufeff")
        raw = raw.replace("\r\n", "\n").replace("\r", "\n")
        raw = unicodedata.normalize("NFKC", raw)
        lines = [line.rstrip() for line in raw.split("\n")]
        return "\n".join(lines).strip()

    @staticmethod
    def _read_skill_content(skills_dir: Path, skill_name: str) -> str:
        """Read skill content from disk with path fallback."""
        safe_name = (skill_name or "").strip()
        if not safe_name:
            return ""

        # Preferred layout: app/skills/<name>/skill.md
        candidate_dir_file = skills_dir / safe_name / "skill.md"
        if candidate_dir_file.exists():
            return candidate_dir_file.read_text(encoding="utf-8").strip()

        # Backward-compatible layout: app/skills/<name>.md
        candidate_file = skills_dir / f"{safe_name}.md"
        if candidate_file.exists():
            return candidate_file.read_text(encoding="utf-8").strip()
        return ""

    @staticmethod
    def _load_tool_schema(tool_name: str) -> Optional[Dict[str, Any]]:
        try:
            module_name = resolve_module(tool_name)
            schema_module = importlib.import_module(f"app.tools.{module_name}.schema")
            schema = getattr(schema_module, "SCHEMA", None)
            if isinstance(schema, dict):
                return schema
        except Exception as exc:
            logger.warning(f"[AgentEngine] Failed to load schema for '{tool_name}': {exc}")
        return None

    def _bind_tools(self, tool_names: List[str]) -> List[Dict[str, Any]]:
        bound_tools: List[Dict[str, Any]] = []
        seen = set()
        for name in tool_names:
            if name in seen:
                continue
            seen.add(name)
            schema = self._load_tool_schema(name)
            if schema is None:
                logger.warning(f"[AgentEngine] Warning: Tool '{name}' not found in app/tools.")
                continue
            bound_tools.append(schema)
        return bound_tools

    def _effective_tools(self, ctx: ConversationContext) -> List[Dict[str, Any]]:
        if ctx.disable_support_tools:
            return []

        filtered: List[Dict[str, Any]] = []
        for schema in self.tools:
            name = str(((schema or {}).get("function") or {}).get("name", "")).strip()
            if name == "memory_recall" and ctx.disable_memory_recall:
                continue
            if name == "memory_store" and ctx.disable_memory_store:
                continue
            filtered.append(schema)
        return filtered

    @staticmethod
    def _inject_current_time_context(ctx: ConversationContext) -> None:
        tz_name = (os.getenv("APP_TIMEZONE", "Asia/Shanghai") or "Asia/Shanghai").strip() or "Asia/Shanghai"
        weekdays_cn = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        try:
            tz = ZoneInfo(tz_name)
            now = datetime.now(tz)
        except Exception:
            tz_name = "UTC"
            now = datetime.now(timezone.utc)
        ctx.current_time_local = now.strftime("%Y-%m-%d %H:%M:%S")
        ctx.current_time_iso = now.isoformat()
        ctx.current_timezone = tz_name
        ctx.current_weekday_local = weekdays_cn[now.weekday()]

    def build_context_aware_prompt(self, ctx: ConversationContext) -> str:
        self._inject_current_time_context(ctx)
        # 1. Load soul personality
        from app.core.agent.soul import SoulManager

        soul_content = SoulManager.get_soul(ctx.soul)

        # 2. Load agent-specific behavior
        agent_behavior = super().build_context_aware_prompt(ctx)

        # 3. Build combined system prompt structure
        base = (
            "[PROMPT CONTRACT]\n"
            "- SOUL defines speaking style only.\n"
            "- AGENT ROLE defines responsibilities, boundaries, and decision rules.\n"
            "- If style guidance conflicts with role safety/rules, follow role safety/rules.\n\n"
            "- Follow LANGUAGE POLICY strictly: reply in user's language and keep tool text arguments in user's language.\n\n"
            f"[SOUL - UNIFIED PERSONALITY]:\n{soul_content}\n\n"
            f"[AGENT ROLE & BEHAVIOR]:\n{agent_behavior}"
        )

        handoff_text = self._build_handoff_instructions()
        if not self.skill_blocks:
            return self._normalize_prompt_text(base + handoff_text)
        skills_text = "\n\n".join(self.skill_blocks)
        combined = (
            f"{base}\n\n"
            "[SKILLS - CONTEXT GUIDELINES, NOT TOOLS]:\n"
            f"{skills_text}\n"
            f"{handoff_text}"
        )
        return self._normalize_prompt_text(combined)

    def _build_handoff_instructions(self) -> str:
        if not self.allowed_handoffs:
            return ""
        allowed = ", ".join(self.allowed_handoffs)
        return (
            "\n\n[HANDOFF PROTOCOL]:\n"
            f"If another specialist agent should handle the request better, you may hand off only to: {allowed}.\n"
            "When handing off, reply with JSON only using this exact structure:\n"
            '{"kind":"handoff","target_agent":"<allowed_agent>","reason":"short reason"}\n'
            "If you can handle the request yourself, do not emit handoff JSON.\n"
        )

    def allow_handoff(self, target_agent: str) -> bool:
        target = str(target_agent or "").strip()
        return bool(target and target in self.allowed_handoffs)

    def process(
        self,
        query: str,
        context: ConversationContext,
        response_format: Optional[Dict[str, Any]] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> Any:
        """Prepare context and run exactly one LLM call."""
        ctx = context
        ctx.query = query

        if isinstance(messages, list) and messages:
            step_messages = list(messages)
        else:
            base_prompt = self.build_context_aware_prompt(ctx)
            step_messages = self.build_messages(query, ctx, system_prompt_override=base_prompt)
            if isinstance(messages, list):
                messages[:] = step_messages
        active_tools = self._effective_tools(ctx)
        effective_tool_choice = self.first_tool_choice
        if self.response_mode == "handoff_only":
            handoff_tools: List[Dict[str, Any]] = []
            for schema in active_tools:
                name = str(((schema or {}).get("function") or {}).get("name", "")).strip()
                if name == "handoff_tool":
                    handoff_tools.append(schema)
            active_tools = handoff_tools
            effective_tool_choice = "required"

        params: Dict[str, Any] = {
            "model": self.model,
            "messages": step_messages,
            "extra_body": {"enable_thinking": False},
        }
        if active_tools:
            params["tools"] = active_tools
            params["tool_choice"] = effective_tool_choice
        if isinstance(response_format, dict) and response_format:
            params["response_format"] = response_format

        response = self.client.chat.completions.create(**params)
        return response

