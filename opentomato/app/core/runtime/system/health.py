from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import FastAPI

from app.core.config import get_app_settings, is_strict_external_dependencies


def _set_check(
    checks: Dict[str, Dict[str, Any]],
    name: str,
    ok: bool,
    detail: str,
    required: bool = True,
) -> None:
    checks[name] = {
        "ok": ok,
        "required": required,
        "detail": detail,
    }


def evaluate_runtime_dependencies(app: FastAPI) -> Dict[str, Any]:
    strict = is_strict_external_dependencies()
    checks: Dict[str, Dict[str, Any]] = {}



    settings = get_app_settings()
    llm_api_key = bool(getattr(settings, "llm_api_key", ""))
    _set_check(
        checks,
        "llm",
        llm_api_key,
        "Configured." if llm_api_key else "Missing DASHSCOPE_API_KEY.",
    )

    memory_service = getattr(app.state, "memory", None)
    memory_expected = bool(getattr(memory_service, "expected_enabled", False)) if memory_service else False
    memory_enabled = bool(getattr(memory_service, "enabled", False)) if memory_service else False
    memory_required = strict and memory_expected
    if not memory_expected:
        _set_check(
            checks,
            "memory",
            True,
            "Disabled by OPENVIKING_ENABLED=false.",
            required=False,
        )
    elif not memory_enabled:
        _set_check(
            checks,
            "memory",
            False,
            "Provider not initialized.",
            required=memory_required,
        )
    else:
        try:
            memory_ok = bool(memory_service.openviking.health())
            _set_check(
                checks,
                "memory",
                memory_ok,
                "Health check passed." if memory_ok else "Health check failed.",
                required=memory_required,
            )
        except Exception as exc:
            _set_check(
                checks,
                "memory",
                False,
                f"Health check failed: {exc}",
                required=memory_required,
            )

    ready = all(item["ok"] or not item["required"] for item in checks.values())
    return {
        "ready": ready,
        "strict": strict,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }
