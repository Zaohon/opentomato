from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from app.core.memory.service import MemoryService


@dataclass
class ToolRuntimeDeps:
    tools_handler: Any
    memory_service: Optional[MemoryService] = None


ToolResult = Tuple[str, Optional[Dict[str, Any]]]
