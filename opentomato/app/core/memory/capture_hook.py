from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from app.core.config.fls_agent import AgentSpec
from app.core.logging import get_logger
from app.core.memory.service import MemoryService
from app.core.text import merge_sections

if TYPE_CHECKING:
    from app.core.runtime.chat.chat_runtime import ChatRuntime

logger = get_logger("app.runtime.memory_hook")


@dataclass
class MemoryAfterResult:
    captured: bool = False
    stored: bool = False
    extracted_count: int = 0
    warning: str = ""
    logs: List[str] = field(default_factory=list)


def collect_used_contexts(response_data: Dict[str, object]) -> List[str]:
    contexts: List[str] = []
    artifact_contexts = response_data.get("used_contexts", [])
    if isinstance(artifact_contexts, list):
        contexts.extend(str(item or "").strip() for item in artifact_contexts if str(item or "").strip())
    seen = set()
    ordered: List[str] = []
    for item in contexts:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def build_long_term_turn_record(
    *,
    request_id: str,
    user_id: str,
    session_id: str,
    query: str,
    response_data: Dict[str, object],
    default_agent_name: str,
    used_contexts: List[str],
    used_skills: List[Dict[str, Any]],
    explicit_memory_store: bool,
    auto_capture_hit: bool,
) -> Dict[str, Any]:
    return {
        "schema_version": "v1",
        "request_id": request_id,
        "user_id": user_id,
        "session_id": session_id,
        "agent": {
            "current": str(response_data.get("current_agent", default_agent_name) or default_agent_name),
            "route_path": str(response_data.get("route_path", "") or ""),
            "handoff_trace": list(response_data.get("handoff_trace", []))
            if isinstance(response_data.get("handoff_trace", []), list)
            else [],
        },
        "turn": {
            "user_text": query,
            "assistant_text": str(response_data.get("response", "") or ""),
            "final_response_kind": str(response_data.get("kind", "final") or "final"),
        },
        "usage": {
            "contexts": list(used_contexts),
            "skills": list(used_skills),
        },
        "signals": {
            "explicit_memory_store": explicit_memory_store,
            "auto_capture_hit": auto_capture_hit,
            "has_tool_usage": bool(used_skills),
            "high_value_turn": bool(used_skills or used_contexts or auto_capture_hit),
        },
    }


def _extract_memory_store_result(response_data: Dict[str, object]) -> Dict[str, object]:
    action_log = response_data.get("action_log", {})
    action_log = action_log if isinstance(action_log, dict) else {}
    memory_store_action = action_log.get("memory_store", {})
    memory_store_action = memory_store_action if isinstance(memory_store_action, dict) else {}
    memory_store_result = memory_store_action.get("result", {})
    return memory_store_result if isinstance(memory_store_result, dict) else {}


def _memory_store_completed(memory_store_result: Dict[str, object]) -> bool:
    return bool(
        memory_store_result.get("enqueued", False)
        or memory_store_result.get("stored", False)
        or memory_store_result.get("append_ok", False)
        or memory_store_result.get("commit_ok", False)
    )


class MemoryAutoCaptureHook:
    order = 140

    def __init__(self, memory_service: Optional[MemoryService]) -> None:
        self.memory_service = memory_service

    def run(self, state: "ChatRuntime") -> None:
        if self.memory_service is None or not bool(getattr(self.memory_service, "enabled", False)):
            return
        if state.ctx.disable_memory_store:
            return
        query = str(state.query or "").strip()
        if not query:
            return
        capture = self.memory_service.policy.should_auto_capture(query)
        if not capture.enabled or not capture.text:
            return

        logger.info(
            f"[MemoryPolicy] auto_capture user={state.user_id} "
            f"reason={capture.reason} fact={capture.text}"
        )
        store_result = self.memory_service.store_explicit_fact(
            user_id=state.user_id,
            session_id=state.session_id,
            text=str(capture.text or "").strip(),
        )
        warning = str((store_result or {}).get("warning", "") or "").strip()
        state.ctx.disable_memory_store = True
        state.artifacts["auto_capture_hit"] = True
        state.artifacts["auto_capture_text"] = str(capture.text or "").strip()
        state.artifacts["auto_capture_warning"] = warning
        section = (
            "[SYSTEM AUTO CAPTURE]\n"
            f"Queued durable user fact for async long-term memory ingestion: {capture.text}\n"
            f"store_warning: {warning or 'none'}"
        )
        state.ctx.rag_context = merge_sections(state.ctx.rag_context, section)


class MemoryCaptureHook:
    order = 400

    def __init__(self, memory_service: Optional[MemoryService]) -> None:
        self.memory_service = memory_service

    def run(self, state: "ChatRuntime") -> None:
        spec = state.artifacts.get("final_agent_spec") or state.artifacts.get("agent_spec")
        if not isinstance(spec, AgentSpec):
            return
        if self.memory_service is None or not spec.execution.bind_memory:
            return
        response_data = dict(state.final_payload or {})
        response_data["handoff_trace"] = list(state.handoff_trace)
        response_data["current_agent"] = state.current_agent
        response_data["route_path"] = state.route_path
        response_data["used_contexts"] = list(state.artifacts.get("used_contexts", []))
        result = self._capture(
            query=state.query,
            response_data=response_data,
            state=state,
            spec=spec,
        )
        for line in result.logs:
            logger.info(line)

    def _capture(
        self,
        *,
        query: str,
        response_data: Dict[str, object],
        state: "ChatRuntime",
        spec: AgentSpec,
    ) -> MemoryAfterResult:
        result = MemoryAfterResult()
        memory_store_result = _extract_memory_store_result(response_data)
        explicit_store_done = _memory_store_completed(memory_store_result)
        auto_capture_attempted = bool(state.ctx.disable_memory_store)
        used_skills: List[Dict[str, Any]] = []
        used_contexts = collect_used_contexts(response_data)

        turn_record = build_long_term_turn_record(
            request_id=state.ctx.request_id,
            user_id=state.ctx.user_id,
            session_id=state.ctx.session_id,
            query=query,
            response_data=response_data,
            default_agent_name=spec.logical_name,
            used_contexts=used_contexts,
            used_skills=used_skills,
            explicit_memory_store=explicit_store_done,
            auto_capture_hit=auto_capture_attempted,
        )

        if explicit_store_done:
            result.logs.append(
                f"[MemoryLifecycle] skip_session_append_after_explicit_store user={state.ctx.user_id} "
                f"session={state.ctx.session_id or 'default'}"
            )
        else:
            self._enqueue_turn_record(
                result=result,
                state=state,
                turn_record=turn_record,
                used_contexts=used_contexts,
                used_skills=used_skills,
            )
        return result

    def _enqueue_turn_record(
        self,
        *,
        result: MemoryAfterResult,
        state: "ChatRuntime",
        turn_record: Dict[str, object],
        used_contexts: List[str],
        used_skills: List[Dict[str, object]],
    ) -> None:
        if self.memory_service is None:
            return
        append_result = self.memory_service.append_session_records(
            user_id=state.ctx.user_id,
            session_id=state.ctx.session_id,
            turn_record=turn_record,
        )
        append_ok = bool((append_result or {}).get("append_ok", False))
        append_warning = str((append_result or {}).get("warning", "") or "")
        if not append_ok:
            return
        result.captured = True
        result.stored = False
        result.extracted_count = 0
        result.warning = append_warning
        result.logs.append(
            f"[MemoryLifecycle] append_session_records user={state.ctx.user_id} "
            f"append_ok=true contexts={len(used_contexts)} skills={len(used_skills)} "
            f"warning={append_warning or 'none'}"
        )

