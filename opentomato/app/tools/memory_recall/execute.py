from typing import Any, Dict

from app.core.agent.context import ConversationContext
from app.core.tools_handler.types import ToolRuntimeDeps, ToolResult


def run(args: Dict[str, Any], ctx: ConversationContext, deps: ToolRuntimeDeps) -> ToolResult:
    tool_query = str(args.get("query", "") or "").strip()
    user_query = str(getattr(ctx, "query", "") or "").strip()
    if tool_query and user_query:
        q = f"{tool_query} {user_query}".strip()
    else:
        q = tool_query or user_query
    if deps.memory_service is None:
        return "", None
    bundle = deps.memory_service.recall_bundle(
        query=q,
        user_id=ctx.user_id,
        session_id=ctx.session_id,
        query_text_for_rank=user_query or q,
        caller="tool_memory_recall",
    )
    return str(bundle.get("rendered", "") or ""), None




