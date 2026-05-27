from typing import Dict, Any
from app.core.config import get_app_settings
from app.core.config.fls_agent import AgentRegistry, load_agent_registry
from app.core.agent.engine import AgentEngine
from app.core.memory.service import MemoryService
from openai import OpenAI

class AgentManager:
    def __init__(self, memory_service: MemoryService, tools_handler: Any):
        settings = get_app_settings()
        if not settings.llm_api_key:
            raise RuntimeError("DASHSCOPE_API_KEY not found.")
        self.registry = load_agent_registry()
        self.agent_instances: Dict[str, Any] = {}
        for logical_name, spec in self.registry.agents.items():
            client = OpenAI(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
            )
            agent = AgentEngine(
                spec,
                client,
                tools_handler=tools_handler if spec.execution.bind_tools else None,
                model=spec.default_model,
                memory_service=memory_service if spec.execution.bind_memory else None,
                allowed_handoffs=list(spec.allowed_handoff),
                response_mode=spec.execution.response_mode,
                default_handoff=spec.execution.default_handoff,
                first_tool_choice=spec.execution.initial_tool_choice,
            )
            self.agent_instances[logical_name] = agent
        self.default_agent = self.registry.main_agent if self.registry.main_agent in self.agent_instances else "router"
        self.max_handoffs = max(self.registry.max_handoffs, 0)
        self.allowed_handoffs = {name: list(spec.allowed_handoff) for name, spec in self.registry.agents.items()}

    def describe(self) -> dict:
        return {
            "default_agent": self.default_agent,
            "max_handoffs": self.max_handoffs,
            "agent_names": sorted(self.agent_instances.keys()),
            "agents_loaded": len(self.agent_instances),
            "allowed_handoffs": self.allowed_handoffs,
        }
