from __future__ import annotations

import base64
import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from openai import OpenAI
from pydantic import BaseModel

from app.core.config import get_app_settings

router = APIRouter()


class VoiceRequest(BaseModel):
    audio_base64: str
    audio_mime_type: Optional[str] = "audio/webm"
    enable_itn: bool = False
    model: Optional[str] = None


class VoiceResponse(BaseModel):
    text: str
    model: str


def _to_data_uri(audio_base64: str, audio_mime_type: str) -> str:
    payload = str(audio_base64 or "").strip()
    mime = str(audio_mime_type or "audio/webm").strip() or "audio/webm"
    if payload.startswith("data:"):
        return payload
    try:
        base64.b64decode(payload, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid audio_base64: {exc}")
    return f"data:{mime};base64,{payload}"


@router.post("/voice", response_model=VoiceResponse)
async def voice_endpoint(request: VoiceRequest) -> VoiceResponse:
    settings = get_app_settings()
    if not settings.llm_api_key:
        raise HTTPException(status_code=500, detail="Missing LLM API key.")

    model = (
        str(request.model or "").strip()
        or os.getenv("ASR_MODEL", "").strip()
        or "qwen3-asr-flash"
    )
    data_uri = _to_data_uri(request.audio_base64, request.audio_mime_type or "audio/webm")

    try:
        client = OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {"data": data_uri},
                        }
                    ],
                }
            ],
            stream=False,
            extra_body={
                "asr_options": {
                    "enable_itn": bool(request.enable_itn),
                }
            },
        )
        text = str(getattr(completion.choices[0].message, "content", "") or "").strip()
        return VoiceResponse(text=text, model=model)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"voice_recognition_failed: {exc}")

