"""ToolsHandler runtime container."""

from app.core.tools_handler.registry import load_all_tools


class ToolsHandler:
    """
    Runtime dependency container for tools.

    Tool-specific business logic lives in app/tools/<tool>/.
    """

    def __init__(
        self,
    ):
        self.tool_map = load_all_tools()
        self._tool_names = tuple(sorted(self.tool_map.keys()))

    def get_tool_names(self):
        return list(self._tool_names)
