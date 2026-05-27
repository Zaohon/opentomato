from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from app.core.agent.context import ConversationContext
from app.core.logging import get_logger, log_timing
from app.core.runtime.chat.hooks import (
    DispatchAgentHook,
    FinalAnswerHook,
    MemoryAutoCaptureHook,
    MemoryCaptureHook,
    MemoryFindHook,
    MemorySummaryLoadHook,
    SessionLoadHook,
    SessionPersistHook,
)
from app.core.runtime.chat.hooks.base import RuntimeHook
from app.core.runtime.chat.phase_manager import PhaseManager
from app.core.runtime.chat.phases import RuntimePhase

if TYPE_CHECKING:
    from fastapi import FastAPI


logger = get_logger("app.runtime.chat_runtime")
DEFAULT_RESPONSE = "I'm sorry, I couldn't process that."


class ChatRuntime:
    def __init__(
        self,
        *,
        app: "FastAPI",
        user_input: str,
        user_id: str,
        soul: str,
        entry_agent_name: Optional[str] = None,
        skip_session_load: bool = False,
        skip_session_persist: bool = False,
        response_format: Optional[Dict[str, Any]] = None,
        final_answer_system: Optional[str] = None,
        emit_fallback: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.app = app
        self._emit_fallback: Optional[Callable[[str], None]] = emit_fallback
        self.ctx: ConversationContext = ConversationContext(
            user_id=user_id,
            request_id="",
            session_id=user_id,
            query=str(user_input or ""),
            user_language=self._detect_user_language(str(user_input or "")),
            chat_history=[],  # 禁止外部传入历史消息，统一由phase流程加载
            memory_summary_md="",
            soul=soul,
        )
        self.entry_agent_name: str = (
            str(entry_agent_name or "").strip()
            or self.app.state.agent_manager.default_agent
        )
        self.response_format: Optional[Dict[str, Any]] = (
            dict(response_format) if isinstance(response_format, dict) else None
        )
        self.final_answer_system: str = str(final_answer_system or "").strip()
        self.route_path: str = ""
        self.current_agent: str = ""
        self.handoff_trace: List[Dict[str, Any]] = []
        self.action_log: Dict[str, Any] = {}
        self.final_response: str = ""
        self.final_payload: Dict[str, Any] = {}
        self.errors: List[str] = []
        self.flags: Dict[str, Any] = {}
        self.metrics: Dict[str, Any] = {}
        self.artifacts: Dict[str, Any] = {}
        self.skip_session_load: bool = bool(skip_session_load)
        self.skip_session_persist: bool = bool(skip_session_persist)
        self.phase_manager = PhaseManager()

        memory_service = app.state.memory
        session_store = app.state.session_store
        summary_hook = MemorySummaryLoadHook(memory_service)
        find_hook = MemoryFindHook(memory_service)
        auto_capture_hook = MemoryAutoCaptureHook(memory_service)
        final_answer_hook = FinalAnswerHook()
        capture_hook = MemoryCaptureHook(memory_service)

        self.add_hook(RuntimePhase.LOAD_USER_SUMMARY, summary_hook)
        self.add_hook(RuntimePhase.LOAD_CHAT_HISTORY, SessionLoadHook(session_store))
        self.add_hook(RuntimePhase.FIND_MEMORY, find_hook)
        self.add_hook(RuntimePhase.CAPTURE_MEMORY, auto_capture_hook)
        self.add_hook(RuntimePhase.DISPATCH_AGENT, DispatchAgentHook())
        self.add_hook(RuntimePhase.FINAL_ANSWER, final_answer_hook)
        self.add_hook(RuntimePhase.SAVE_MEMORY, capture_hook)
        self.add_hook(RuntimePhase.SAVE_MEMORY, SessionPersistHook(session_store))

    def add_hook(self, phase: RuntimePhase, hook: RuntimeHook) -> None:
        self.phase_manager.add_hook(phase, hook)

    @property
    def request_id(self) -> str:
        return str(self.ctx.request_id or "")

    @property
    def user_id(self) -> str:
        return str(self.ctx.user_id or "")

    @property
    def session_id(self) -> str:
        return str(self.ctx.session_id or "")

    @property
    def query(self) -> str:
        return str(self.ctx.query or "")

    @property
    def chat_history(self) -> List[Dict[str, str]]:
        return list(self.ctx.chat_history) if isinstance(self.ctx.chat_history, list) else []

    @chat_history.setter
    def chat_history(self, value: List[Dict[str, str]]) -> None:
        self.ctx.chat_history = list(value) if isinstance(value, list) else []

    @property
    def memory_summary_md(self) -> str:
        return str(self.ctx.memory_summary_md or "")

    @memory_summary_md.setter
    def memory_summary_md(self, value: str) -> None:
        self.ctx.memory_summary_md = str(value or "")

    @staticmethod
    def _detect_user_language(text: str) -> str:
        raw = str(text or "").strip()
        if not raw:
            return "zh-CN"
        for ch in raw:
            code = ord(ch)
            if 0x4E00 <= code <= 0x9FFF:
                return "zh-CN"
            if 0x3040 <= code <= 0x30FF:
                return "ja-JP"
            if 0xAC00 <= code <= 0xD7AF:
                return "ko-KR"
        if all(ord(ch) < 128 for ch in raw):
            return "en-US"
        return "zh-CN"

    def emit_state(self, text: str) -> None:
        if self._emit_fallback is None:
            return
        try:
            self._emit_fallback(str(text or "").strip())
        except Exception:
            pass

    def _run_phase(self, phase: RuntimePhase) -> None:
        with log_timing(
            logger,
            "runtime.phase.total",
            phase=phase.value,
        ):
            for hook in self.phase_manager.get_hooks(phase):
                hook.run(self)

    def run(self) -> Dict[str, object]:
        agent_manager = self.app.state.agent_manager
        resolved_entry_agent = self.entry_agent_name
        request_id = uuid.uuid4().hex

        self.ctx.request_id = request_id
        self.current_agent = resolved_entry_agent
        request_started = time.time()

        with log_timing(
            logger,
            "runtime.request",
        ):
            self.emit_state("正在加载用户摘要")
            self._run_phase(RuntimePhase.LOAD_USER_SUMMARY)
            self.emit_state("正在加载会话历史")
            self._run_phase(RuntimePhase.LOAD_CHAT_HISTORY)
            self.emit_state("正在检索记忆")
            self._run_phase(RuntimePhase.FIND_MEMORY)
            self.emit_state("正在寻找有价值的记忆")
            self._run_phase(RuntimePhase.CAPTURE_MEMORY)
            self.emit_state("正在思考问题...")
            self._run_phase(RuntimePhase.DISPATCH_AGENT)
            self.emit_state("调度执行完成")
            routed = self.artifacts["dispatch_result"]
            self.route_path = str(routed["path"])
            self.action_log = routed["action_log"]
            self.final_response = str(routed["response"])
            self.final_payload = routed
            self.current_agent = str(routed["final_agent"])
            self.handoff_trace = routed["handoff_trace"]

            final_answer_messages = routed.get("final_answer_messages", [])
            if isinstance(final_answer_messages, list):
                self.artifacts["final_answer_messages"] = final_answer_messages

            routed_contexts = routed.get("used_contexts", [])
            if isinstance(routed_contexts, list):
                merged_contexts: List[str] = []
                seen = set()
                for item in list(self.artifacts.get("used_contexts", [])) + routed_contexts:
                    uri = str(item or "").strip()
                    if not uri or uri in seen:
                        continue
                    seen.add(uri)
                    merged_contexts.append(uri)
                self.artifacts["used_contexts"] = merged_contexts

            final_agent = agent_manager.agent_instances.get(self.current_agent)
            if final_agent is not None:
                self.artifacts["final_agent_spec"] = getattr(final_agent, "spec", None)

            self.emit_state("正在生成最终回复")
            self._run_phase(RuntimePhase.FINAL_ANSWER)
            self.emit_state("正在持久化记忆")
            self._run_phase(RuntimePhase.SAVE_MEMORY)

            token_usage = self.final_payload.get("token_usage", {}) if isinstance(self.final_payload.get("token_usage", {}), dict) else {}
            prompt_tokens = int(token_usage.get("prompt", 0) or 0)
            completion_tokens = int(token_usage.get("completion", 0) or 0)
            total_tokens = prompt_tokens + completion_tokens
            elapsed_ms = int((time.time() - request_started) * 1000)
            logger.info(
                "chat_completed user=%s query=%s response=%s elapsed_ms=%s path=%s tokens=[P=%s/C=%s/T=%s]",
                self.user_id,
                self.query,
                self.final_response,
                elapsed_ms,
                self.route_path,
                prompt_tokens,
                completion_tokens,
                total_tokens,
            )

            return {
                "response": self.final_response,
                "path": self.route_path,
                "action_log": self.action_log,
                "request_id": self.request_id,
                "session_id": self.session_id,
                "token_usage": token_usage,
            }
