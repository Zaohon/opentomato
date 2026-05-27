"""Runtime tool executor entrypoint."""

import importlib
from typing import Any, Dict

from app.core.agent.context import ConversationContext
from app.core.tools_handler.registry import resolve_module
from app.core.tools_handler.types import ToolRuntimeDeps, ToolResult


def run_tool(tool_name: str, args: Dict[str, Any], ctx: ConversationContext, deps: ToolRuntimeDeps) -> ToolResult:
    module_name = resolve_module(tool_name)
    executor = importlib.import_module(f"app.tools.{module_name}.execute")
    run_fn = getattr(executor, "run", None)
    if not callable(run_fn):
        return f"Tool '{tool_name}' executor is not callable.", None
    return run_fn(args=args, ctx=ctx, deps=deps)





