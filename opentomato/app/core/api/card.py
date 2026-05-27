from typing import Any, Dict, Optional, List
import json
import re

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.core.api.validators import validate_request_params
from app.core.logging import get_logger
from app.core.runtime import ChatRuntime

router = APIRouter()
logger = get_logger("app.api.card")


CARD_RESPONSE_FORMAT: Dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "chat_card_output",
        "strict": True,
        "schema": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "subtitle": {"type": "string"},
                    "detail": {"type": "string"},
                    "card": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": True,
                        },
                    },
                },
                "required": ["title", "subtitle", "detail", "card"],
                "additionalProperties": False,
            },
        },
    },
}

CARD_FINAL_ANSWER_SYSTEM = (
    "You must output JSON only. Output a single JSON array. "
    "Do not include markdown or explanations. "
    "Each item must contain exactly four fields: title, subtitle, detail, card. "
    "card must be an array (card[]). "
    "If no card content, return card as empty array."
)


class ChatCardRequest(BaseModel):
    message: str
    user_id: str
    soul: str


def _extract_json_array(raw: str) -> Optional[list]:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass
    matches = list(re.finditer(r"\[[\s\S]*\]", text))
    for match in matches:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, list):
                return parsed
        except Exception:
            continue
    return None


def _normalize_cards(raw_items: list) -> list[Dict[str, Any]]:
    normalized: list[Dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "") or "").strip()
        subtitle = str(item.get("subtitle", "") or "").strip()
        detail = str(item.get("detail", "") or "").strip()
        card = item.get("card", [])
        if not isinstance(card, list):
            card = []
        if not title:
            title = "未命名卡片"
        normalized.append(
            {
                "title": title,
                "subtitle": subtitle,
                "detail": detail,
                "card": card,
            }
        )
    return normalized


@router.post("/chat/card/", response_model=List[Dict[str, Any]])
async def chat_card_endpoint(
    request: ChatCardRequest,
    http_request: Request,
):
    try:
        params = validate_request_params(
            user_id=request.user_id,
            soul=request.soul,
            require_soul=True,
        )
        user_id = str(params["user_id"])
        soul_name = str(params["soul"])
        llm: ChatRuntime = ChatRuntime(
            app=http_request.app,
            user_input=request.message,
            user_id=user_id,
            soul=soul_name,
            response_format=CARD_RESPONSE_FORMAT,
            final_answer_system=CARD_FINAL_ANSWER_SYSTEM,
            emit_fallback=None,
        )

        response_payload = await run_in_threadpool(llm.run)
        raw_response = str(response_payload.get("response", "") or "")
        parsed_cards = _extract_json_array(raw_response)
        if parsed_cards is None:
            raise HTTPException(status_code=502, detail="chat_card_output_invalid_json_array")
        cards = _normalize_cards(parsed_cards)

        return cards
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("chat_card_failed user=%s error=%s", getattr(request, "user_id", ""), exc)
        raise HTTPException(status_code=500, detail=str(exc))
