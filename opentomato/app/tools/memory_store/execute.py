from typing import Any, Dict

from app.core.agent.context import ConversationContext
from app.core.tools_handler.types import ToolRuntimeDeps, ToolResult


def run(args: Dict[str, Any], ctx: ConversationContext, deps: ToolRuntimeDeps) -> ToolResult:
    text = args.get("text", "")
    if not text or deps.memory_service is None:
        return "Failed to store memory.", None
    result = deps.memory_service.store_explicit_fact(
        user_id=ctx.user_id,
        session_id=ctx.session_id,
        text=text,
    )
    if not isinstance(result, dict):
        return "Memory stored successfully.", None

    parts = [
        f"stored={bool(result.get('stored', False))}",
        f"append_ok={bool(result.get('append_ok', False))}",
        f"commit_ok={bool(result.get('commit_ok', False))}",
        f"extracted_count={int(result.get('extracted_count', 0) or 0)}",
    ]
    warning = str(result.get("warning", "") or "").strip()
    if warning:
        parts.append(f"warning={warning}")
    return (
        "Memory store result: " + ", ".join(parts),
        {
            "memory_store": {
                "text": text,
                "result": result,
            }
        },
    )




