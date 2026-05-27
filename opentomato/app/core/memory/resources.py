from __future__ import annotations

import json
import os
import queue
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from app.core.config.bools import read_bool_env
from app.core.logging import get_logger
from app.core.memory.provider import OpenVikingContentProvider

logger = get_logger("app.memory.resources.ingest")


class ResourceIngestService:
    """In-process worker queue for ingesting uploaded files into OpenViking resources."""

    def __init__(self, provider: OpenVikingContentProvider):
        self.provider = provider
        self.enabled = self._read_bool("INGEST_ENABLED", default=True)
        self.dropbox_dir = Path((os.getenv("INGEST_DROPBOX_DIR", "/data/dropbox") or "/data/dropbox").strip())
        self.default_target_uri = (
            os.getenv("INGEST_DEFAULT_TARGET_URI", "viking://resources/fls_hems_manual/").strip()
            or "viking://resources/fls_hems_manual/"
        )
        self.max_retry = max(int(os.getenv("INGEST_MAX_RETRY", "3") or "3"), 0)
        self.retry_delay_seconds = max(int(os.getenv("INGEST_RETRY_DELAY_SECONDS", "5") or "5"), 1)
        self.worker_concurrency = max(int(os.getenv("INGEST_WORKER_CONCURRENCY", "1") or "1"), 1)

        self._jobs: "queue.Queue[Optional[Dict[str, Any]]]" = queue.Queue()
        self._stop = threading.Event()
        self._workers: list[threading.Thread] = []

    @staticmethod
    def _read_bool(name: str, default: bool = False) -> bool:
        return read_bool_env(name, default=default)

    def start(self) -> None:
        if not self.enabled:
            logger.info("[IngestWorker] disabled by INGEST_ENABLED=false")
            return
        if self._workers:
            return

        self.dropbox_dir.mkdir(parents=True, exist_ok=True)
        for i in range(self.worker_concurrency):
            t = threading.Thread(target=self._worker_loop, name=f"resource-ingest-{i+1}", daemon=True)
            t.start()
            self._workers.append(t)

        recovered = self.recover_pending_jobs()
        logger.info(
            "[IngestWorker] started enabled=true workers=%s recovered=%s dropbox=%s",
            len(self._workers),
            recovered,
            self.dropbox_dir,
        )

    def stop(self) -> None:
        if not self._workers:
            return
        self._stop.set()
        for _ in self._workers:
            self._jobs.put(None)
        for t in self._workers:
            t.join(timeout=3)
        self._workers.clear()
        logger.info("[IngestWorker] stopped")

    def enqueue_meta_path(self, meta_path: Path | str) -> bool:
        if not self.enabled:
            return False
        try:
            job = self._load_meta(Path(meta_path))
            self._jobs.put(job)
            return True
        except Exception as exc:
            logger.warning("[IngestWorker] enqueue_meta_path failed path=%s error=%s", meta_path, exc)
            return False

    def recover_pending_jobs(self) -> int:
        if not self.enabled:
            return 0
        count = 0
        for meta_path in self.dropbox_dir.glob("*.meta.json"):
            try:
                meta = self._load_meta(meta_path)
            except Exception:
                continue
            status = str(meta.get("status", "") or "").strip().lower()
            if status in {"", "queued", "running", "retry"}:
                meta["status"] = "queued"
                self._write_meta(meta_path, meta)
                self._jobs.put(meta)
                count += 1
        return count

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            try:
                job = self._jobs.get(timeout=1)
            except queue.Empty:
                continue
            if job is None:
                return
            try:
                self._process_job(job)
            except Exception as exc:
                logger.warning("[IngestWorker] unexpected error ingest_id=%s error=%s", job.get("ingest_id", ""), exc)
            finally:
                self._jobs.task_done()

    def _process_job(self, job: Dict[str, Any]) -> None:
        ingest_id = str(job.get("ingest_id", "") or "").strip() or "unknown"
        meta_path = Path(str(job.get("_meta_path", "") or "").strip())
        if not meta_path.exists():
            logger.warning("[IngestWorker] meta missing ingest_id=%s path=%s", ingest_id, meta_path)
            return

        meta = self._load_meta(meta_path)
        file_path = Path(str(meta.get("dropbox_path", "") or "").strip())
        if not file_path.exists():
            meta["status"] = "failed"
            meta["last_error"] = f"file_not_found:{file_path}"
            self._write_meta(meta_path, meta)
            logger.warning("[IngestWorker] file missing ingest_id=%s path=%s", ingest_id, file_path)
            return

        retry_count = int(meta.get("retry_count", 0) or 0)
        meta["status"] = "running"
        meta["updated_at"] = int(time.time())
        self._write_meta(meta_path, meta)

        try:
            result = self._ingest_file_to_openviking(
                file_path=file_path,
                target_uri=str(meta.get("target_uri", "") or "").strip() or self.default_target_uri,
                reason=f"uploaded via hems ingest api ({meta.get('uploader', 'api')})",
            )
            meta["status"] = "success"
            meta["updated_at"] = int(time.time())
            meta["result"] = result
            meta.pop("last_error", None)
            self._write_meta(meta_path, meta)
            self._move_to_bucket("done", file_path=file_path, meta_path=meta_path)
            logger.info("[IngestWorker] success ingest_id=%s file=%s", ingest_id, file_path.name)
            return
        except Exception as exc:
            retry_count += 1
            meta["retry_count"] = retry_count
            meta["updated_at"] = int(time.time())
            meta["last_error"] = str(exc)
            if retry_count > self.max_retry:
                meta["status"] = "failed"
                self._write_meta(meta_path, meta)
                self._move_to_bucket("failed", file_path=file_path, meta_path=meta_path)
                logger.warning(
                    "[IngestWorker] failed ingest_id=%s retry=%s/%s error=%s",
                    ingest_id,
                    retry_count,
                    self.max_retry,
                    exc,
                )
                return

            meta["status"] = "retry"
            self._write_meta(meta_path, meta)
            logger.warning(
                "[IngestWorker] retry ingest_id=%s retry=%s/%s error=%s",
                ingest_id,
                retry_count,
                self.max_retry,
                exc,
            )
            time.sleep(self.retry_delay_seconds)
            self._jobs.put(self._load_meta(meta_path))

    def _ingest_file_to_openviking(self, *, file_path: Path, target_uri: str, reason: str) -> Dict[str, Any]:
        if not self.provider.enabled:
            raise RuntimeError("openviking_disabled")
        if self.provider._client is None:
            raise RuntimeError("openviking_http_client_unavailable")

        api_key = self.provider.resolve_resource_recall_api_key() or self.provider.key_manager.resolve_system_api_key()
        headers = self.provider._build_headers(api_key)

        with file_path.open("rb") as f:
            resp = self.provider._client.post(
                "/api/v1/resources/temp_upload",
                files={"file": (file_path.name, f, "application/octet-stream")},
                data={"telemetry": "false"},
                headers=headers,
                timeout=self.provider.timeout_seconds,
            )
        upload_result = self._extract_result_dict(resp)
        temp_path = str((upload_result or {}).get("temp_path", "") or "").strip()
        if not temp_path:
            raise RuntimeError(f"openviking_temp_upload_missing_temp_path status={resp.status_code}")

        payload: Dict[str, Any] = {
            "temp_path": temp_path,
            "reason": reason,
            "wait": False,
            "telemetry": False,
        }
        if target_uri.endswith("/"):
            payload["parent"] = target_uri
        else:
            payload["to"] = target_uri

        resp2 = self.provider._client.post(
            "/api/v1/resources",
            json=payload,
            headers=headers,
            timeout=self.provider.timeout_seconds,
        )
        result = self._extract_result_dict(resp2)
        if result is None:
            raise RuntimeError(f"openviking_add_resource_failed status={resp2.status_code} body={resp2.text[:300]}")
        return result

    @staticmethod
    def _extract_result_dict(resp: httpx.Response) -> Optional[Dict[str, Any]]:
        if resp.status_code >= 400:
            raise RuntimeError(f"openviking_http_error status={resp.status_code} body={resp.text[:300]}")
        payload = resp.json()
        if not isinstance(payload, dict):
            return None
        result = payload.get("result")
        if isinstance(result, dict):
            return result
        return None

    @staticmethod
    def _load_meta(meta_path: Path) -> Dict[str, Any]:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise RuntimeError("invalid_meta_not_dict")
        data["_meta_path"] = str(meta_path)
        return data

    @staticmethod
    def _write_meta(meta_path: Path, data: Dict[str, Any]) -> None:
        payload = dict(data)
        payload.pop("_meta_path", None)
        tmp = meta_path.with_suffix(meta_path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(meta_path)

    def _move_to_bucket(self, bucket: str, *, file_path: Path, meta_path: Path) -> None:
        target_dir = self.dropbox_dir / str(bucket or "").strip()
        target_dir.mkdir(parents=True, exist_ok=True)
        self._safe_move(file_path, target_dir / file_path.name)
        self._safe_move(meta_path, target_dir / meta_path.name)

    @staticmethod
    def _safe_move(src: Path, dst: Path) -> None:
        if not src.exists():
            return
        if dst.exists():
            stamp = int(time.time())
            dst = dst.with_name(f"{dst.stem}_{stamp}{dst.suffix}")
        shutil.move(str(src), str(dst))
