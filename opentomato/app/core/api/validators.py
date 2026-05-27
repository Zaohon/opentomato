from typing import Any, Dict, Optional

from fastapi import HTTPException

from app.core.config.user_id import normalize_user_id


def validate_request_params(
    *,
    user_id: Optional[str] = None,
    soul: Optional[str] = None,
    require_soul: bool = False,
) -> Dict[str, Any]:
    from app.core.agent.soul import SoulManager

    result: Dict[str, Any] = {}

    if user_id is not None:
        try:
            result["user_id"] = normalize_user_id(user_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    if require_soul:
        soul_name = str(soul or "").strip()
        if not soul_name:
            raise HTTPException(status_code=400, detail="soul is required")
        if not SoulManager.soul_exists(soul_name):
            raise HTTPException(
                status_code=400,
                detail=f"Soul '{soul_name}' not found. Available souls: {list(SoulManager.list_souls().keys())}",
            )
        result["soul"] = soul_name
    return result
