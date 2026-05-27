from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.core.runtime.chat.chat_runtime import ChatRuntime


logger = get_logger("app.runtime.final_answer")


class FinalAnswerHook:
    order = 350

    @staticmethod
    def _is_qwen_model(model_name: str) -> bool:
        return "qwen" in str(model_name or "").strip().lower()

    @staticmethod
    def _extract_json_schema(response_format: Dict[str, Any]) -> Dict[str, Any]:
        if str(response_format.get("type", "") or "").strip().lower() != "json_schema":
            return {}
        schema = ((response_format.get("json_schema") or {}).get("schema") or {})
        return schema if isinstance(schema, dict) else {}

    @staticmethod
    def _build_schema_system_prompt(schema: Dict[str, Any]) -> str:
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            properties = {}
        required = schema.get("required", [])
        if not isinstance(required, list):
            required = []
        required_fields = [str(item).strip() for item in required if str(item).strip()]
        property_fields = [str(name).strip() for name in properties.keys() if str(name).strip()]
        field_hint = ", ".join(required_fields or property_fields)
        if not field_hint:
            field_hint = "请按上游 schema 约束"
        return (
            "You must output JSON only. "
            "Do not include markdown, explanations, or extra text. "
            "Output a single JSON object. "
            f"Fields must follow schema and include: {field_hint}. "
            "Do not add extra fields."
        )

    @staticmethod
    def _prepend_system_message(messages: List[Dict[str, Any]], system_prompt: str) -> List[Dict[str, Any]]:
        prompt = str(system_prompt or "").strip()
        if not prompt:
            return list(messages)
        return [{"role": "system", "content": prompt}] + list(messages)

    @staticmethod
    def _effective_response_format(response_format: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        if FinalAnswerHook._is_qwen_model(model_name):
            return {"type": "json_object"}
        return dict(response_format)

    def run(self, state: "ChatRuntime") -> None:
        response_format = state.response_format
        if not isinstance(response_format, dict) or not response_format:
            return

        messages = state.artifacts.get("final_answer_messages", [])
        if not isinstance(messages, list) or not messages:
            return

        active_agent_name = str(state.current_agent or "").strip()
        if not active_agent_name:
            return
        agent = state.app.state.agent_manager.agent_instances.get(active_agent_name)
        if agent is None:
            return

        try:
            model_name = str(getattr(agent, "model", "") or "")
            schema = self._extract_json_schema(response_format)
            custom_system = str(getattr(state, "final_answer_system", "") or "").strip()
            auto_system = self._build_schema_system_prompt(schema) if schema else ""
            final_system = custom_system or (auto_system if self._is_qwen_model(model_name) else "")
            final_messages = self._prepend_system_message(list(messages), final_system)
            effective_response_format = self._effective_response_format(response_format, model_name)

            raw_response = agent.client.chat.completions.create(
                model=agent.model,
                messages=final_messages,
                response_format=effective_response_format,
                extra_body={"enable_thinking": False},
            )
            llm_message = raw_response.choices[0].message
            content = str(getattr(llm_message, "content", "") or "").strip()
            if content:
                state.final_response = content
                if isinstance(state.final_payload, dict):
                    state.final_payload["response"] = content

            usage = getattr(raw_response, "usage", None)
            if usage is not None and isinstance(state.final_payload, dict):
                token_usage = state.final_payload.get("token_usage", {})
                if not isinstance(token_usage, dict):
                    token_usage = {}
                token_usage["prompt"] = int(token_usage.get("prompt", 0) or 0) + int(
                    getattr(usage, "prompt_tokens", 0) or 0
                )
                token_usage["completion"] = int(token_usage.get("completion", 0) or 0) + int(
                    getattr(usage, "completion_tokens", 0) or 0
                )
                state.final_payload["token_usage"] = token_usage
        except Exception as exc:
            logger.warning(
                "final_answer_format_failed user_id=%s agent=%s error=%s",
                state.user_id,
                active_agent_name,
                exc,
            )
