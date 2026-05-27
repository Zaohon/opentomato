import os

from fastapi import FastAPI

from app.core.agent.manager import AgentManager
from app.core.memory.resources import ResourceIngestService
from app.core.memory.service import MemoryService
from app.core.runtime.system.sessions import InMemorySessionStore
from app.core.tools_handler import ToolsHandler


def init_long_term_memory(app: FastAPI) -> dict:
    """Initialize long-term memory infrastructure."""
    app.state.memory = MemoryService()
    precreate_users = (os.getenv("OPENVIKING_PRECREATE_USERS", "") or "").strip()
    precreate_summary = (
        app.state.memory.precreate_users(raw_users=precreate_users)
        if precreate_users
        else {
            "enabled": bool(getattr(app.state.memory, "enabled", False)),
            "requested": 0,
            "success": 0,
            "failed": 0,
            "status": "skipped",
        }
    )
    return {
        "enabled": bool(getattr(app.state.memory, "enabled", False)),
        "expected_enabled": bool(getattr(app.state.memory, "expected_enabled", False)),
        "precreate": precreate_summary,
    }


def init_resource_library_manager(app: FastAPI) -> dict:
    """Initialize resource library ingestion manager."""
    app.state.resource_ingest = ResourceIngestService(app.state.memory.openviking)
    app.state.resource_ingest.start()
    return {
        "enabled": bool(getattr(app.state.resource_ingest, "enabled", False)),
        "workers": int(getattr(app.state.resource_ingest, "worker_concurrency", 0) or 0),
    }


def init_infrastructure(app: FastAPI) -> dict:
    """Backward-compatible wrapper for legacy call paths."""
    memory_status = init_long_term_memory(app)
    resource_status = init_resource_library_manager(app)
    return {
        "memory": memory_status,
        "resource_ingest": resource_status,
    }


def init_tools(app: FastAPI) -> dict:
    """Load and initialize tools."""
    app.state.tools = ToolsHandler()
    tool_names = app.state.tools.get_tool_names()
    app.state.tool_names = tool_names
    return {"count": len(tool_names), "names": tool_names}


def init_agents_runtime(app: FastAPI) -> dict:
    """Initialize multi-agent runtime."""
    app.state.agent_manager = AgentManager(
        memory_service=app.state.memory,
        tools_handler=app.state.tools,
    )
    tool_names = list(getattr(app.state, "tool_names", []) or [])
    if not tool_names:
        tool_names = app.state.tools.get_tool_names()
    agents_status = app.state.agent_manager.describe()
    agents_status["tools_loaded"] = len(tool_names)
    agents_status["tool_names"] = tool_names
    return agents_status


def init_short_term_memory(app: FastAPI) -> dict:
    """Initialize short-term conversation memory store."""
    app.state.session_store = InMemorySessionStore()
    return {"backend": "in_memory", "ready": True}


def init_runtime(app: FastAPI) -> dict:
    """Backward-compatible wrapper for legacy call paths."""
    agents_status = init_agents_runtime(app)
    session_status = init_short_term_memory(app)
    merged = dict(agents_status)
    merged["session_backend"] = str(session_status.get("backend", "unknown"))
    merged["session_ready"] = bool(session_status.get("ready", False))
    return merged


def shutdown_runtime(app: FastAPI) -> None:
    """Clean up runtime resources."""
    if hasattr(app.state, "resource_ingest") and app.state.resource_ingest is not None:
        app.state.resource_ingest.stop()
    if hasattr(app.state, "memory") and app.state.memory is not None:
        app.state.memory.close()

