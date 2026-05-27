from typing import Any, Dict

from app.core.agent.context import ConversationContext
from app.core.tools_handler.types import ToolRuntimeDeps, ToolResult
from app.tools.energy_flow.service import get_energy_flow


def run(args: Dict[str, Any], ctx: ConversationContext, deps: ToolRuntimeDeps) -> ToolResult:
    _ = args
    _ = deps
    return get_energy_flow(user_id=ctx.user_id), None
