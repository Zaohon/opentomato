from fastapi import FastAPI

from app.core.api.card import router as card_router
from app.core.api.chat import router as chat_router
from app.core.api.resources import router as resources_router
from app.core.api.suggestion import router as suggestion_router
from app.core.api.system import router as system_router
from app.core.api.voice import router as voice_router


def register_api(app: FastAPI) -> None:
    app.include_router(chat_router, prefix="/api/v1")
    app.include_router(card_router, prefix="/api/v1")
    app.include_router(resources_router, prefix="/api/v1")
    app.include_router(suggestion_router, prefix="/api/v1")
    app.include_router(voice_router, prefix="/api/v1")
    app.include_router(system_router)


__all__ = ["register_api"]
