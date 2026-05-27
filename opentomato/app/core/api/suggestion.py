import json
import re
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.core.api.validators import validate_request_params
from app.core.logging import get_logger
from app.core.runtime import ChatRuntime

router = APIRouter()
logger = get_logger("app.api.suggestion")

SUGGESTION_RESPONSE_FORMAT: Dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "suggestion_output",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "brief": {"type": "string"},
                "detail": {"type": "string"},
            },
            "required": ["brief", "detail"],
            "additionalProperties": False,
        },
    },
}

SUGGESTION_FINAL_ANSWER_SYSTEM = (
    "You must output JSON only. Output a single JSON object. "
    "Do not include markdown or explanations. "
    "The object must contain only two string fields: brief and detail."
)


class GenerateSuggestionRequest(BaseModel):
    user_id: str


class GenerateSuggestionResponse(BaseModel):
    user_id: str
    brief: str
    detail: str


class HandleSuggestionRequest(BaseModel):
    detail_message: str
    user_id: Optional[str] = None


class HandleSuggestionResponse(BaseModel):
    ok: bool
    message: str
    echo_detail: str
    user_id: str = ""

def _extract_json_object(raw: str) -> Optional[Dict[str, Any]]:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    matches = re.findall(r"\{[\s\S]*\}", text)
    for candidate in matches:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue
    return None


def _normalize_suggestion(raw: str) -> Dict[str, str]:
    parsed = _extract_json_object(raw)
    if parsed is None:
        raise ValueError("suggestion output is not a JSON object")

    brief = str(parsed.get("brief", "") or "").strip()
    detail = str(parsed.get("detail", "") or "").strip()
    if not brief or not detail:
        raise ValueError("suggestion output missing required fields: brief/detail")

    return {"brief": brief[:200], "detail": detail[:2000]}


@router.post("/generate_suggestion", response_model=GenerateSuggestionResponse)
async def generate_suggestion_endpoint(request: GenerateSuggestionRequest, http_request: Request):
    params = validate_request_params(user_id=request.user_id)
    user_id = str(params["user_id"])
    soul_name = "default"

    llm: ChatRuntime = ChatRuntime(
        app=http_request.app,
        user_input=(
            "请为当前用户生成一条节能建议。"
            "内容需要可执行、具体，并给出简要原因。"
        ),
        user_id=user_id,
        soul=soul_name,
        entry_agent_name="suggestion_agent",
        skip_session_load=True,
        skip_session_persist=True,
        response_format=SUGGESTION_RESPONSE_FORMAT,
        final_answer_system=SUGGESTION_FINAL_ANSWER_SYSTEM,
        emit_fallback=None,
    )
    try:
        response_payload = await run_in_threadpool(llm.run)
        raw_response = str(response_payload.get("response", "") or "")
        suggestion = _normalize_suggestion(raw_response)
        return GenerateSuggestionResponse(
            user_id=user_id,
            brief=suggestion["brief"],
            detail=suggestion["detail"],
        )
    except Exception as exc:
        logger.exception("generate_suggestion_failed user=%s error=%s", user_id, exc)
        raise HTTPException(
            status_code=502,
            detail="generate_suggestion_output_invalid",
        )


@router.post("/handle_suggestion", response_model=HandleSuggestionResponse)
async def handle_suggestion_endpoint(request: HandleSuggestionRequest):
    raw_detail = str(request.detail_message or "").strip()
    if not raw_detail:
        raise HTTPException(status_code=400, detail="detail_message is required")

    safe_user_id = ""
    if request.user_id is not None and str(request.user_id).strip():
        params = validate_request_params(user_id=request.user_id)
        safe_user_id = str(params["user_id"])

    return HandleSuggestionResponse(
        ok=True,
        message="suggestion handled (mock)",
        echo_detail=raw_detail,
        user_id=safe_user_id,
    )
