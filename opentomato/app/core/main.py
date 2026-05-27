import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.api import register_api
from app.core.config import get_cors_allow_origins
from app.core.logging import (
    build_uvicorn_log_config,
    configure_app_logging,
    get_logger,
    install_print_logging_bridge,
)
from app.core.runtime import build_lifespan

# Initialize unified application logging and bridge legacy print statements.
configure_app_logging()
install_print_logging_bridge()

logger = get_logger("app.startup")

app = FastAPI(
    title="AI-HEMS Agent API",
    description="Enterprise-grade Home Energy Management System Agent",
    version="1.0.0",
    lifespan=build_lifespan(logger),
)

cors_origins = get_cors_allow_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=(cors_origins != ["*"]),
    allow_methods=["*"],
    allow_headers=["*"],
)

register_api(app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.core.main:app",
        host=os.getenv("UVICORN_HOST", "0.0.0.0"),
        port=int(os.getenv("UVICORN_PORT", "8000")),
        reload=os.getenv("UVICORN_RELOAD", "false").strip().lower() in {"1", "true", "yes", "on"},
        log_config=build_uvicorn_log_config(),
    )

