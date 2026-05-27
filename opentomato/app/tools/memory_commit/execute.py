from typing import Any, Dict

from app.core.agent.context import ConversationContext
from app.core.tools_handler.types import ToolRuntimeDeps, ToolResult


def run(args: Dict[str, Any], ctx: ConversationContext, deps: ToolRuntimeDeps) -> ToolResult:
    reason = str(args.get("reason", "") or "").strip() or "tool_requested_commit"
    if deps.memory_service is None:
        return "memory_commit unavailable: memory service disabled.", None
    result = deps.memory_service.commit_session_now(
        user_id=ctx.user_id,
        session_id=ctx.session_id,
        force=True,
    )
    if not isinstance(result, dict):
        return "memory_commit failed: invalid result.", None
    commit_ok = bool(result.get("commit_ok", False))
    extracted_count = int(result.get("extracted_count", 0) or 0)
    warning = str(result.get("warning", "") or "")
    msg = (
        f"memory_commit commit_ok={commit_ok} extracted_count={extracted_count} "
        f"reason={reason}"
    )
    if warning:
        msg += f" warning={warning}"
    return msg, {"memory_commit": {"reason": reason, "result": result}}
