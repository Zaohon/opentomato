from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

from app.core.agent.context import ConversationContext
from app.core.logging import get_logger

logger = get_logger("app.agent")


class BaseAgent(ABC):
    """
    Abstract Base Class for all HEMS Agents.
    Enforces a standard interface for initialization and execution.
    """

    def __init__(self, client: OpenAI, model: str = "qwen-plus"):
        """
        Initialize the agent with an LLM client and model.

        Args:
            client: The OpenAI compatible client (DashScope).
            model: The model name to use for this agent.
        """
        self.client = client
        self.model = model
        self.name = "BaseAgent"
        self.system_prompt = "You are a helpful assistant."
        self.tools = []

    def get_effective_system_prompt(self, user_id: str = "default") -> str:
        """
        Get final system prompt.
        """
        _ = user_id
        return self.system_prompt

    def build_context_aware_prompt(self, ctx: ConversationContext) -> str:
        """Build system prompt with profile + RAG context."""
        base = self.get_effective_system_prompt(ctx.user_id)
        return (
            base
            + ctx.language_policy_prompt_section
            + ctx.current_time_prompt_section
            + ctx.memory_summary_prompt_section
            + ctx.rag_prompt_section
        )

    def build_messages(
        self,
        query: str,
        ctx: ConversationContext,
        system_prompt_override: Optional[str] = None,
    ) -> list:
        """Build the standard [system, ...chat_history, user] message array."""
        prompt = system_prompt_override or self.build_context_aware_prompt(ctx)
        messages = [{"role": "system", "content": prompt}]
        if ctx.chat_history:
            messages.extend(ctx.chat_history)
        messages.append({"role": "user", "content": query})
        return messages

    @abstractmethod
    def process(
        self,
        query: str,
        context: ConversationContext,
        response_format: Optional[Dict[str, Any]] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> Any:
        """
        Process the user query and return a result.

        Args:
            query: The user's input text.
            context: ConversationContext.
            response_format: Optional structured output constraint passed to model API.
            messages: Optional prebuilt message list for iterative runtime loops.

        Returns:
            Provider raw response object for runtime-level orchestration.
        """
        pass

    def _handle_tool_call(
        self,
        func_name: str,
        args: Dict[str, Any],
        ctx: ConversationContext,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Dispatch a single tool call. Subclasses override to add their tools.

        Returns:
            (result_content, optional_action_log_entry) tuple.
        """
        return f"Unknown tool: {func_name}", None

    def allow_handoff(self, target_agent: str) -> bool:
        """Whether this agent allows handoff to the given target agent."""
        _ = target_agent
        return False
