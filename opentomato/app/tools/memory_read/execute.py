from typing import Any, Dict

from app.core.agent.context import ConversationContext
from app.core.tools_handler.types import ToolRuntimeDeps, ToolResult


def run(args: Dict[str, Any], ctx: ConversationContext, deps: ToolRuntimeDeps) -> ToolResult:
    uri = str(args.get("uri", "") or "").strip()
    level = str(args.get("level", "overview") or "overview").strip().lower()
    if deps.memory_service is None:
        return "memory_read unavailable: memory service disabled.", None
    result = deps.memory_service.read_memory(
        user_id=ctx.user_id,
        uri=uri,
        level=level,
    )
    if not isinstance(result, dict):
        return "memory_read failed: invalid result.", None
    ok = bool(result.get("ok", False))
    warning = str(result.get("warning", "") or "")
    content = str(result.get("content", "") or "")
    head = f"memory_read ok={ok} level={result.get('level', level)} uri={result.get('uri', uri)}"
    if warning:
        head += f" warning={warning}"
    if not content:
        return head, None
    return f"{head}\n{content}", None
