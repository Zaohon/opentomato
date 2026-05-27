from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.runtime import evaluate_runtime_dependencies

router = APIRouter()


@router.get("/healthz", include_in_schema=False)
def liveness_check():
    return {"status": "ok"}


@router.get("/readyz", include_in_schema=False)
def readiness_check(request: Request):
    report = evaluate_runtime_dependencies(request.app)
    request.app.state.readiness_report = report
    return JSONResponse(status_code=200 if report["ready"] else 503, content=report)
