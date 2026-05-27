from typing import Any, Dict

from app.core.agent.context import ConversationContext
from app.core.tools_handler.types import ToolRuntimeDeps, ToolResult
from app.tools.station_forecast.service import get_station_forecast_24h


def run(args: Dict[str, Any], ctx: ConversationContext, deps: ToolRuntimeDeps) -> ToolResult:
    _ = ctx
    _ = deps
    station_id = args.get("station_id", 1)
    return get_station_forecast_24h(station_id=station_id), None

