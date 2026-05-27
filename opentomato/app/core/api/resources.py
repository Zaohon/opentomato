import json
import os
import re
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from app.core.logging import get_logger

router = APIRouter()
logger = get_logger("app.api.resources")

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
_DEFAULT_ALLOWED_EXTS = {".pdf", ".doc", ".docx", ".txt", ".md", ".ppt", ".pptx", ".xls", ".xlsx"}


class IngestUploadResponse(BaseModel):
    accepted: bool
    ingest_id: str
    filename: str
    bytes: int
    dropbox_path: str
    target_uri: str
    status: str = "queued"


def _safe_filename(raw_name: str) -> str:
    base = Path(str(raw_name or "").strip()).name
    if not base:
        return "upload.bin"
    return _SAFE_NAME_RE.sub("_", base)


def _resolve_allowed_exts() -> set[str]:
    raw = (os.getenv("INGEST_ALLOWED_EXTENSIONS", "") or "").strip()
    if not raw:
        return set(_DEFAULT_ALLOWED_EXTS)
    values = {("." + item.strip().lstrip(".")).lower() for item in raw.split(",") if item.strip()}
    return values or set(_DEFAULT_ALLOWED_EXTS)


@router.post("/resources/upload", response_model=IngestUploadResponse)
async def ingest_upload_endpoint(
    request: Request,
    file: UploadFile = File(...),
    target_uri: str = Form("viking://resources/fls_hems_manual/"),
    uploader: str = Form("api"),
):
    if file is None:
        raise HTTPException(status_code=400, detail="file is required")

    dropbox_dir = Path((os.getenv("INGEST_DROPBOX_DIR", "/data/dropbox") or "/data/dropbox").strip())
    max_mb = max(int(os.getenv("INGEST_UPLOAD_MAX_MB", "1024") or "1024"), 1)
    max_bytes = max_mb * 1024 * 1024
    allowed_exts = _resolve_allowed_exts()

    original_name = str(file.filename or "").strip()
    safe_name = _safe_filename(original_name)
    ext = Path(safe_name).suffix.lower()
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported file extension: {ext or 'none'}",
        )

    try:
        dropbox_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"cannot prepare dropbox dir: {exc}")

    ingest_id = uuid.uuid4().hex
    stored_name = f"{int(time.time())}_{ingest_id[:8]}_{safe_name}"
    stored_path = dropbox_dir / stored_name
    bytes_written = 0

    try:
        with stored_path.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > max_bytes:
                    out.close()
                    stored_path.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail=f"file too large, max={max_mb}MB")
                out.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"failed to save file: {exc}")
    finally:
        try:
            await file.close()
        except Exception:
            pass

    meta = {
        "ingest_id": ingest_id,
        "original_name": original_name,
        "stored_name": stored_name,
        "dropbox_path": str(stored_path),
        "target_uri": str(target_uri or "").strip() or "viking://resources/fls_hems_manual/",
        "uploader": str(uploader or "api").strip() or "api",
        "bytes": bytes_written,
        "uploaded_at": int(time.time()),
        "status": "queued",
        "retry_count": 0,
    }
    meta_path: Path | None = stored_path.with_suffix(stored_path.suffix + ".meta.json")
    try:
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("[IngestUpload] metadata_write_failed ingest_id=%s path=%s error=%s", ingest_id, meta_path, exc)
        meta_path = None

    ingest_worker = getattr(request.app.state, "resource_ingest", None)
    if ingest_worker is not None and meta_path is not None:
        queued = bool(ingest_worker.enqueue_meta_path(meta_path))
        if not queued:
            logger.warning("[IngestUpload] queue_enqueue_failed ingest_id=%s meta=%s", ingest_id, meta_path)

    logger.info(
        "[IngestUpload] accepted ingest_id=%s file=%s bytes=%s target=%s path=%s",
        ingest_id,
        safe_name,
        bytes_written,
        meta["target_uri"],
        stored_path,
    )
    return IngestUploadResponse(
        accepted=True,
        ingest_id=ingest_id,
        filename=safe_name,
        bytes=bytes_written,
        dropbox_path=str(stored_path),
        target_uri=meta["target_uri"],
        status="queued",
    )
