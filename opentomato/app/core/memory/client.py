import os
import threading
import time
from typing import Any, Dict, Optional

import httpx

from app.core.config.bools import read_bool_env
from app.core.config import is_strict_external_dependencies
from app.core.logging import get_logger

from .key_manager import OpenVikingKeyManager
from .openviking_api import OpenVikingAPI

logger = get_logger("app.memory.openviking.client")


class OpenVikingClientBase:
    """
    OpenViking HTTP wrapper for profile/persona/long-term memory persistence.

    Multi-tenant: each business user maps to an independent OpenViking account
    (1 account = 1 user). Account IDs are derived as ``account_{sanitized_user_id}``.
    """

    _ACCOUNT_PREFIX = "account_"
    _RETRIABLE_ERROR_SNIPPETS = (
        "connection reset by peer",
        "server disconnected without sending a response",
        "timed out",
        "timeout",
        "temporarily unavailable",
    )

    def __init__(self):
        self.strict_dependencies = is_strict_external_dependencies()
        self.expected_enabled = self._read_bool("OPENVIKING_ENABLED", default=True)
        self.url = os.getenv("OPENVIKING_URL", "").strip().rstrip("/")
        self.api_key = os.getenv("OPENVIKING_API_KEY", "").strip()
        self.root_api_key = os.getenv("OPENVIKING_ROOT_API_KEY", "").strip()
        self.strong_isolation_requested = self._read_bool("OPENVIKING_STRONG_ISOLATION", default=True)
        self._legacy_account_id = self._sanitize_segment(
            os.getenv("OPENVIKING_ACCOUNT_ID", "memory-agent").strip() or "memory-agent"
        )
        self.shared_account_id = self._sanitize_segment(
            os.getenv("OPENVIKING_SHARED_ACCOUNT_ID", self._legacy_account_id).strip() or self._legacy_account_id
        )
        self.account_admin_user_id = self._sanitize_segment(
            os.getenv("OPENVIKING_ACCOUNT_ADMIN_USER_ID", "memory-admin").strip() or "memory-admin"
        )
        self.account_user_role = (os.getenv("OPENVIKING_ACCOUNT_USER_ROLE", "user").strip() or "user").lower()
        self.resource_recall_api_key = os.getenv("OPENVIKING_RESOURCE_API_KEY", "").strip()
        self.agent_id = os.getenv("OPENVIKING_AGENT_ID", "memory-backend").strip()
        self.timeout_seconds = float(os.getenv("OPENVIKING_TIMEOUT_SECONDS", "60"))
        self.search_limit = int(os.getenv("OPENVIKING_MEMORY_SEARCH_LIMIT", "10"))
        self.recall_timeout_seconds = max(float(os.getenv("OPENVIKING_RECALL_TIMEOUT_SECONDS", "10")), 0.5)
        self.session_commit_every_n = max(int(os.getenv("OPENVIKING_SESSION_COMMIT_EVERY_N", "10")), 1)
        self.session_commit_max_age_seconds = max(
            int(os.getenv("OPENVIKING_SESSION_COMMIT_MAX_AGE_SECONDS", "600")),
            30,
        )
        self.idle_commit_enabled = self._read_bool("MEMORY_IDLE_COMMIT_ENABLED", default=True)
        self.idle_commit_seconds = max(int(os.getenv("MEMORY_IDLE_COMMIT_SECONDS", "60")), 5)

        self._client: Optional[httpx.Client] = None
        self._memory_session_state: Dict[str, Dict[str, float]] = {}
        self._memory_session_timers: Dict[str, threading.Timer] = {}
        self.strong_isolation_enabled = False
        self.enabled = False
        self.key_manager = OpenVikingKeyManager(self)

        if not self.expected_enabled:
            logger.warning("[OpenViking] Disabled by OPENVIKING_ENABLED=false")
            return

        if not self.url:
            msg = "OPENVIKING_URL is required when OPENVIKING_ENABLED=true."
            if self.strict_dependencies:
                raise RuntimeError(msg)
            logger.warning("[OpenViking] %s Provider disabled.", msg)
            return

        if self.strong_isolation_requested:
            if self.root_api_key:
                self.strong_isolation_enabled = True
            else:
                msg = (
                    "OPENVIKING_STRONG_ISOLATION=true but OPENVIKING_ROOT_API_KEY is not configured. "
                    "Falling back to shared API key mode."
                )
                if self.strict_dependencies:
                    raise RuntimeError(msg)
                logger.warning("[OpenViking] %s", msg)

        self._client = httpx.Client(base_url=self.url, timeout=self.timeout_seconds)
        self.enabled = True
        logger.info(
            "[OpenViking] Enabled. url=%s, strong_isolation=%s, "
            "account_mode=%s, recall_timeout=%ss, session_commit_every_n=%s, "
            "session_commit_max_age_seconds=%ss, idle_commit=%s:%ss, resource_identity=%s",
            self.url,
            "on" if self.strong_isolation_enabled else "off",
            "per_user_account" if self.strong_isolation_enabled else f"shared_account:{self.shared_account_id}",
            self.recall_timeout_seconds,
            self.session_commit_every_n,
            self.session_commit_max_age_seconds,
            "on" if self.idle_commit_enabled else "off",
            self.idle_commit_seconds,
            "explicit_api_key" if self.resource_recall_api_key else "inherit_user_identity",
        )

    @staticmethod
    def _read_bool(name: str, default: bool = False) -> bool:
        return read_bool_env(name, default=default)

    @staticmethod
    def _sanitize_segment(value: str) -> str:
        return "".join(c if c.isalnum() or c in {"-", "_"} else "_" for c in value)

    @staticmethod
    def _is_missing_path_error(exc: Exception) -> bool:
        text = str(exc).lower()
        return (
            "no such file" in text
            or "no such file or directory" in text
            or "not found" in text
            or "read:" in text and "not found" in text
        )

    @classmethod
    def _is_retriable_request_error(cls, exc: Exception) -> bool:
        text = str(exc).lower()
        return any(snippet in text for snippet in cls._RETRIABLE_ERROR_SNIPPETS)

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def health(self) -> bool:
        if not self.enabled or self._client is None:
            return False
        try:
            response = self._client.get(OpenVikingAPI.HEALTH)
            if not response.is_success:
                return False
            payload = response.json()
            return payload.get("status") == "ok"
        except Exception:
            return False

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        allow_not_found: bool = False,
        user_id: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ) -> Any:
        if not self.enabled or self._client is None:
            raise RuntimeError("OpenViking provider is disabled.")

        should_retry_auth = bool(user_id) and not api_key
        should_retry_read = method.upper() == "GET"
        normalized_path = str(path or "").strip()
        should_retry_write = method.upper() == "POST" and (
            normalized_path.startswith(OpenVikingAPI.SESSIONS_PREFIX)
            or normalized_path.startswith(OpenVikingAPI.SEARCH_PREFIX)
        )
        max_attempts = 2 if (should_retry_auth or should_retry_read or should_retry_write) else 1
        response: Optional[httpx.Response] = None
        last_status_code: Any = ""

        started = time.perf_counter()
        request_failed = False
        try:
            for attempt in range(max_attempts):
                resolved_api_key = self.key_manager.resolve_request_api_key(user_id=user_id, api_key=api_key)
                headers = self._build_headers(resolved_api_key)
                try:
                    response = self._client.request(
                        method,
                        path,
                        params=params,
                        json=json_body,
                        headers=headers,
                        timeout=timeout_seconds if timeout_seconds is not None else self.timeout_seconds,
                    )
                    last_status_code = response.status_code
                except Exception as exc:
                    if (should_retry_read or should_retry_write) and attempt < max_attempts - 1 and self._is_retriable_request_error(exc):
                        time.sleep(0.2 * (attempt + 1))
                        continue
                    raise RuntimeError(f"OpenViking request failed: {exc}") from exc

                if response.status_code == 401 and should_retry_auth and attempt == 0:
                    self.key_manager.invalidate_cached_user_key(user_id or "")
                    continue
                if (should_retry_read or should_retry_write) and attempt < max_attempts - 1 and response.status_code >= 500:
                    time.sleep(0.2 * (attempt + 1))
                    continue
                break
        except Exception:
            request_failed = True
            raise
        finally:
            duration_ms = int((time.perf_counter() - started) * 1000)
            status = "失败" if request_failed else "成功"
            logger.debug(
                "[耗时] 名称=openviking.request 状态=%s 总耗时：=%s毫秒 method=%s path=%s user_id=%s attempts=%s status_code=%s",
                status,
                duration_ms,
                method.upper(),
                path,
                user_id or "",
                max_attempts,
                last_status_code,
            )

        if response is None:
            raise RuntimeError("OpenViking request failed with empty response.")

        payload: Dict[str, Any] = {}
        try:
            payload = response.json()
        except Exception:
            payload = {}

        if response.status_code == 404 and allow_not_found:
            return None

        if isinstance(payload, dict) and payload.get("status") == "error":
            err = payload.get("error", {}) or {}
            code = (err.get("code") or "UNKNOWN").upper()
            message = err.get("message") or response.text
            if allow_not_found and code == "NOT_FOUND":
                return None
            raise RuntimeError(f"OpenViking error ({code}): {message}")

        if not response.is_success:
            if allow_not_found and response.status_code == 404:
                return None
            raise RuntimeError(f"OpenViking HTTP error: {response.status_code} {response.text[:200]}")

        if isinstance(payload, dict):
            return payload.get("result")
        return payload

    def _build_headers(self, api_key: str) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        key = (api_key or "").strip()
        if key:
            headers["X-API-Key"] = key
        # 恢复 agent header，因为 OpenViking 的底层搜索（如语义抽取）默认会依赖并检索 Agent 空间
        if self.agent_id:
            headers["X-OpenViking-Agent"] = self.agent_id
        return headers

    def resolve_resource_recall_api_key(self) -> str:
        return (self.resource_recall_api_key or "").strip()
