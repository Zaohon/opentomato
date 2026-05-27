from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Dict, List

from app.core.logging import get_logger, log_timing
from app.core.tools_handler.executor import run_tool
from app.core.tools_handler.types import ToolRuntimeDeps

if TYPE_CHECKING:
    from app.core.runtime.chat.chat_runtime import ChatRuntime


DEFAULT_RESPONSE = "I'm sorry, I couldn't process that."
logger = get_logger("app.runtime.chat_runtime")
agent_logger = get_logger("app.agent")


class DispatchAgentHook:
    order = 300

    def run(self, state: "ChatRuntime") -> None:
        agent_manager = state.app.state.agent_manager
        entry_agent = str(state.current_agent or "").strip()
        agent = agent_manager.agent_instances[entry_agent]
        state.artifacts["agent_name"] = entry_agent
        state.artifacts["agent_spec"] = getattr(agent, "spec", None)
        state.current_agent = entry_agent
        state.artifacts["dispatch_result"] = self.dispatch(state)

    def dispatch(self, state: "ChatRuntime") -> Dict[str, Any]:
        with log_timing(agent_logger, "dispatch.total"):
            agent_manager = state.app.state.agent_manager
            state.current_agent = str(state.current_agent or "").strip()
            max_handoffs = max(int(agent_manager.max_handoffs or 0), 0)
            max_tool_rounds = 8
            token_prompt_total = 0
            token_completion_total = 0
            aggregated_used_contexts: List[str] = []
            seen_used_contexts = set()
            handoff_count = 0
            state.handoff_trace = [{"step": 1, "agent": state.current_agent, "event": "entry"}]
            state.action_log = {}

            active_agent_instance = agent_manager.agent_instances[state.current_agent]

            messages: List[Dict[str, Any]] = []
            round_index = 0

            while True:
                with log_timing(
                    agent_logger,
                    "dispatch.llm_call",
                    agent=active_agent_instance.name,
                    round_index=round_index,
                ):
                    raw_response = active_agent_instance.process(
                        state.query,
                        state.ctx,
                        messages=messages,
                    )
                usage = getattr(raw_response, "usage", None)
                token_prompt_total += int(getattr(usage, "prompt_tokens", 0) or 0) if usage is not None else 0
                token_completion_total += int(getattr(usage, "completion_tokens", 0) or 0) if usage is not None else 0
                choice = raw_response.choices[0]
                llm_message = choice.message
                content = str(getattr(llm_message, "content", "") or "")
                tool_calls = list(getattr(llm_message, "tool_calls", []) or [])

                if tool_calls:
                    round_index += 1
                    if round_index > max_tool_rounds:
                        return {
                            "response": "[System Error] Tool rounds exceeded max_tool_rounds.",
                            "path": "guard:max_tool_rounds",
                            "action_log": state.action_log,
                            "final_agent": state.current_agent,
                            "handoff_trace": state.handoff_trace,
                            "token_usage": {"prompt": token_prompt_total, "completion": token_completion_total},
                        }

                    messages.append(llm_message)
                    handoff_call = None
                    for call in tool_calls:
                        func_name = str(getattr(getattr(call, "function", None), "name", "") or "").strip()
                        if func_name == "handoff_tool":
                            handoff_call = call
                            break

                    if handoff_call is not None:
                        with log_timing(
                            agent_logger,
                            "dispatch.handoff",
                            from_agent=state.current_agent,
                            round_index=round_index,
                        ):
                            try:
                                handoff_args = json.loads(getattr(getattr(handoff_call, "function", None), "arguments", "{}"))
                            except Exception:
                                handoff_args = {}
                            if not isinstance(handoff_args, dict):
                                handoff_args = {}

                            target_agent = str(handoff_args.get("target_agent", "") or "").strip()
                            reason = str(handoff_args.get("reason", "") or "").strip()
                            if bool(getattr(active_agent_instance, "allow_handoff", lambda _: False)(target_agent)):
                                next_agent_name = target_agent
                                handoff_reason = reason or "Router tool decision."
                            else:
                                next_agent_name = str(getattr(active_agent_instance, "default_handoff", "") or "support_agent")
                                handoff_reason = "Default fallback for unstructured interaction."

                        if handoff_count >= max_handoffs:
                            logger.warning(
                                "agent_handoff_exceeded max_handoffs=%s final_agent=%s user_id=%s",
                                agent_manager.max_handoffs,
                                state.current_agent,
                                state.ctx.user_id,
                            )
                            return {
                                "response": "[System Error] Handoff exceeded max_handoffs.",
                                "path": "guard:max_handoffs",
                                "action_log": state.action_log,
                                "final_agent": state.current_agent,
                                "handoff_trace": state.handoff_trace,
                                "token_usage": {"prompt": token_prompt_total, "completion": token_completion_total},
                            }

                        state.emit_state(handoff_reason)
                        logger.info(
                            "agent_handoff from_agent=%s to_agent=%s step=%s user_id=%s reason=%s",
                            state.current_agent,
                            next_agent_name,
                            handoff_count + 1,
                            state.ctx.user_id,
                            handoff_reason,
                        )
                        state.handoff_trace.append(
                            {
                                "step": handoff_count + 1,
                                "from_agent": state.current_agent,
                                "to_agent": next_agent_name,
                                "reason": handoff_reason,
                                "event": "handoff",
                            }
                        )

                        if not bool(getattr(active_agent_instance, "allow_handoff", lambda _: False)(next_agent_name)):
                            logger.warning(
                                "agent_handoff_blocked from_agent=%s to_agent=%s step=%s user_id=%s",
                                state.current_agent,
                                next_agent_name,
                                handoff_count + 1,
                                state.ctx.user_id,
                            )
                            return {
                                "response": f"[System Error] Handoff blocked by config: {state.current_agent} -> {next_agent_name}",
                                "path": "guard:handoff_blocked",
                                "action_log": state.action_log,
                                "final_agent": state.current_agent,
                                "handoff_trace": state.handoff_trace,
                                "token_usage": {"prompt": token_prompt_total, "completion": token_completion_total},
                            }

                        handoff_count += 1
                        state.current_agent = next_agent_name
                        active_agent_instance = agent_manager.agent_instances.get(state.current_agent)
                        if active_agent_instance is None:
                            return {
                                "response": f"[System Error] Unknown agent '{state.current_agent}' selected.",
                                "path": "guard:unknown_agent",
                                "action_log": state.action_log,
                                "final_agent": state.current_agent,
                                "handoff_trace": state.handoff_trace,
                                "token_usage": {"prompt": token_prompt_total, "completion": token_completion_total},
                            }

                        messages = []
                        round_index = 0
                        continue

                    with log_timing(
                        agent_logger,
                        "dispatch.tools.round",
                        agent=active_agent_instance.name,
                        round_index=round_index,
                        tool_count=len(tool_calls),
                    ):
                        for call in tool_calls:
                            func_name = str(getattr(getattr(call, "function", None), "name", "") or "").strip()
                            tool_id = str(getattr(call, "id", "") or "")
                            try:
                                args = json.loads(getattr(getattr(call, "function", None), "arguments", "{}"))
                            except Exception:
                                args = {}
                            if not isinstance(args, dict):
                                args = {}

                            reason = f"正在调用工具 {func_name}"
                            agent_logger.info(
                                "tool_prepare agent=%s tool=%s round=%s user_id=%s reason=%s args=%s",
                                active_agent_instance.name,
                                func_name,
                                round_index,
                                state.ctx.user_id,
                                reason,
                                json.dumps(args, ensure_ascii=False, sort_keys=True),
                            )
                            state.emit_state(reason)
                            with log_timing(
                                agent_logger,
                                "tool.call",
                                agent=active_agent_instance.name,
                                tool=func_name,
                                round_index=round_index,
                                user_id=state.ctx.user_id,
                            ):
                                try:
                                    state.ctx.agent_name = active_agent_instance.spec.logical_name
                                    deps = ToolRuntimeDeps(
                                        tools_handler=active_agent_instance.tools_handler,
                                        memory_service=active_agent_instance.memory_service,
                                    )
                                    result_content, tool_action = run_tool(func_name, args, state.ctx, deps)
                                except Exception as exc:
                                    result_content, tool_action = f"Tool '{func_name}' execution failed: {exc}", None
                            if tool_action:
                                state.action_log.update(tool_action)
                            messages.append(
                                {
                                    "tool_call_id": tool_id,
                                    "role": "tool",
                                    "name": func_name,
                                    "content": str(result_content),
                                }
                            )
                    continue

                for item in list(state.artifacts.get("used_contexts", [])):
                    uri = str(item or "").strip()
                    if not uri or uri in seen_used_contexts:
                        continue
                    seen_used_contexts.add(uri)
                    aggregated_used_contexts.append(uri)

                with log_timing(
                    agent_logger,
                    "dispatch.finalize",
                    agent=active_agent_instance.name,
                    round_index=round_index,
                ):
                    final_response = str(content or DEFAULT_RESPONSE)
                    final_answer_messages = list(messages)
                    final_answer_messages.append({"role": "assistant", "content": final_response})
                    return {
                        "response": final_response,
                        "path": f"route:{state.current_agent}",
                        "action_log": state.action_log,
                        "final_agent": state.current_agent,
                        "handoff_trace": state.handoff_trace,
                        "used_contexts": aggregated_used_contexts,
                        "final_answer_messages": final_answer_messages,
                        "token_usage": {"prompt": token_prompt_total, "completion": token_completion_total},
                    }

