"""Tool registry for app/tools/* modules."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Dict

from app.core.logging import get_logger


TOOL_MODULE_MAP: Dict[str, str] = {}
logger = get_logger("app.tools.registry")
_LOADED = False


def load_all_tools(force_reload: bool = False) -> Dict[str, str]:
    """Scan app/tools and build function_name -> module_name mapping from schema.py."""
    global _LOADED
    if _LOADED and not force_reload:
        return dict(TOOL_MODULE_MAP)

    TOOL_MODULE_MAP.clear()
    tools_root = Path(__file__).resolve().parents[2] / "tools"
    discovered_tools = 0

    if tools_root.exists():
        for child in sorted(tools_root.iterdir(), key=lambda item: item.name):
            if not child.is_dir():
                continue

            module_name = child.name
            if module_name.startswith("_") or module_name == "__pycache__":
                continue

            schema_file = child / "schema.py"
            if not schema_file.exists():
                logger.warning("[ToolsRegistry] skipped module=%s reason=missing_schema", module_name)
                continue

            try:
                schema_module = importlib.import_module(f"app.tools.{module_name}.schema")
            except Exception as exc:
                logger.warning("[ToolsRegistry] schema_load_failed module=%s error=%s", module_name, exc)
                continue

            schema = getattr(schema_module, "SCHEMA", None)
            if not isinstance(schema, dict):
                logger.warning("[ToolsRegistry] skipped module=%s reason=invalid_schema", module_name)
                continue

            function = schema.get("function", {})
            function_name = function.get("name")
            if not isinstance(function_name, str) or not function_name.strip():
                logger.warning("[ToolsRegistry] skipped module=%s reason=missing_function_name", module_name)
                continue

            normalized_name = function_name.strip()
            existing_module = TOOL_MODULE_MAP.get(normalized_name)
            if existing_module and existing_module != module_name:
                raise RuntimeError(
                    f"Duplicate tool name '{normalized_name}' declared by '{existing_module}' and '{module_name}'."
                )

            TOOL_MODULE_MAP[normalized_name] = module_name
            discovered_tools += 1

    _LOADED = True
    logger.info("[ToolsRegistry] loaded count=%s names=%s", discovered_tools, sorted(TOOL_MODULE_MAP))
    return dict(TOOL_MODULE_MAP)


def resolve_module(tool_name: str) -> str:
    if not _LOADED:
        load_all_tools()
    if tool_name not in TOOL_MODULE_MAP:
        raise KeyError(f"Unknown tool: {tool_name}")
    return TOOL_MODULE_MAP[tool_name]
