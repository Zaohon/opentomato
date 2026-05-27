from typing import Any, Dict, Optional
import asyncio
import json
import threading
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.core.logging import get_logger
from app.core.memory.service import MemoryService
from app.core.runtime import ChatRuntime
from app.core.runtime.system.sessions import SessionStore
from app.core.api.validators import validate_request_params

router = APIRouter()
logger = get_logger("app.api.chat")


class ChatHistoryMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    user_id: str
    soul: str  # Soul personality name (required)


class ChatResponse(BaseModel):
    response: str
    session_id: str


class ChatHistoryResponse(BaseModel):
    user_id: str
    session_id: str
    history: list[ChatHistoryMessage]
    summary: str = ""
    updated_at: float = 0.0


class ResetChatSessionRequest(BaseModel):
    user_id: str
    session_id: Optional[str] = None


class ResetChatSessionResponse(BaseModel):
    user_id: str
    previous_session_id: str
    session_id: str = ""
    cleared: bool
    commit_ok: bool
    extracted_count: int = 0
    warning: str = ""


def _sse_data_frame(data: Dict[str, Any]) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    http_request: Request,
):
    start_time = time.time()
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
            emit_fallback=None,
        )

        logger.info(f"收到user {user_id} 的对话请求,消息为：{request.message}, soul : {soul_name}")

        response_payload = await run_in_threadpool(llm.run)
        elapsed = (time.time() - start_time) * 1000
        response_text = str(response_payload.get("response", ""))
        token_usage = response_payload.get("token_usage", {})
        prompt_tokens = int((token_usage or {}).get("prompt", 0) or 0)
        completion_tokens = int((token_usage or {}).get("completion", 0) or 0)
        total_tokens = prompt_tokens + completion_tokens
        logger.info(
            f"对话请求完成 user={user_id} soul={soul_name} "
            f"message={request.message} 总耗时={elapsed:.0f}ms "
            f"path={response_payload.get('path', '')} "
            f"tokens=[P={prompt_tokens}/C={completion_tokens}/T={total_tokens}] "
            f"回复={response_text}"
        )

        return ChatResponse(
            response=str(response_payload.get("response", "")),
            session_id=str(response_payload.get("session_id", "") or ""),
        )
    except HTTPException:
        raise
    except Exception as exc:
        elapsed = (time.time() - start_time) * 1000
        logger.error(f"[API:ERROR] chat_request user_id={getattr(request, 'user_id', 'unknown')} error={str(exc)} elapsed_ms={elapsed:.0f}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/chat/stream")
async def chat_stream_endpoint(
    request: ChatRequest,
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
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()

        def _emit_packet(payload: Dict[str, Any]) -> None:
            packet = dict(payload or {})
            loop.call_soon_threadsafe(queue.put_nowait, packet)

        def emit(message: str) -> None:
            _emit_packet(
                {
                    "type": "state",
                    "status": "progress",
                    "message": str(message or "").strip(),
                }
            )

        llm: ChatRuntime = ChatRuntime(
            app=http_request.app,
            user_input=request.message,
            user_id=user_id,
            soul=soul_name,
            emit_fallback=emit,
        )

        logger.info(f"收到user {user_id} 的流式对话请求,消息为：{request.message}, soul : {soul_name}")

        def worker() -> None:
            emit("请求已接收，开始处理")
            try:
                response_payload = llm.run()
                _emit_packet(
                    {
                        "type": "result",
                        "status": "done",
                        "response": str(response_payload.get("response", "")),
                        "session_id": str(response_payload.get("session_id", "") or ""),
                    }
                )
            except Exception as exc:
                _emit_packet(
                    {
                        "type": "error",
                        "status": "error",
                        "message": str(exc),
                    }
                )
            finally:
                _emit_packet({"type": "done", "status": "done"})

        threading.Thread(target=worker, daemon=True).start()

        async def stream_packets():
            while True:
                packet = await queue.get()
                yield _sse_data_frame(packet)
                packet_type = str(packet.get("type", "") or "")
                if packet_type in {"done", "error"}:
                    break

        return StreamingResponse(
            stream_packets(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/souls")
async def list_souls_endpoint():
    """List all available soul personalities."""
    from app.core.agent.soul import SoulManager

    souls = SoulManager.list_souls()
    default = SoulManager.get_default_soul_name()
    return {
        "default": default,
        "count": len(souls),
        "souls": {name: description for name, description in souls.items()},
    }


@router.get("/chat/history", response_model=ChatHistoryResponse)
async def chat_history_endpoint(
    http_request: Request,
    user_id: str,
    session_id: Optional[str] = None,
):
    try:
        params = validate_request_params(user_id=user_id)
        safe_user_id = str(params["user_id"])
        session_store: SessionStore = http_request.app.state.session_store

        _ = session_id
        snapshot = session_store.load(safe_user_id, user_id=safe_user_id)
        return ChatHistoryResponse(
            user_id=safe_user_id,
            session_id=safe_user_id,
            history=[
                ChatHistoryMessage(
                    role=str(item.get("role", "") or ""),
                    content=str(item.get("content", "") or ""),
                )
                for item in snapshot.recent_turns
                if isinstance(item, dict)
            ],
            summary=str(snapshot.summary or ""),
            updated_at=float(snapshot.updated_at or 0.0),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/chat/reset", response_model=ResetChatSessionResponse)
async def reset_chat_session_endpoint(
    request: ResetChatSessionRequest,
    http_request: Request,
):
    try:
        params = validate_request_params(user_id=request.user_id)
        safe_user_id = str(params["user_id"])
        memory_service: MemoryService = http_request.app.state.memory
        session_store: SessionStore = http_request.app.state.session_store

        logger.info(f"[API] chat_reset_request user={safe_user_id} session_id={safe_user_id}")
        resolved_session_id = safe_user_id

        commit_result = {
            "commit_ok": True,
            "extracted_count": 0,
            "warning": "no_active_session",
        }
        if resolved_session_id:
            commit_result = await run_in_threadpool(
                memory_service.openviking.commit_user_memory_session,
                safe_user_id,
                resolved_session_id,
                True,
            )

        cleared_snapshot = session_store.clear(
            user_id=safe_user_id,
            session_id=resolved_session_id,
        )
        cleared = bool(resolved_session_id) and str(cleared_snapshot.session_id or "").strip() == resolved_session_id
        return ResetChatSessionResponse(
            user_id=safe_user_id,
            previous_session_id=resolved_session_id,
            session_id=safe_user_id,
            cleared=cleared,
            commit_ok=bool(commit_result.get("commit_ok", False)),
            extracted_count=int(commit_result.get("extracted_count", 0) or 0),
            warning=str(commit_result.get("warning", "") or ""),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
