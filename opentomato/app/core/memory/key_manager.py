from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional

from app.core.config.user_id import normalize_user_id
from app.core.logging import get_logger
from .openviking_api import OpenVikingAPI

if TYPE_CHECKING:
    from .client import OpenVikingClientBase


logger = get_logger("app.memory.openviking.key_manager")


class OpenVikingKeyManager:
    """Manage OpenViking tenant identities and per-user API key caching."""

    def __init__(self, client: "OpenVikingClientBase") -> None:
        self.client = client
        self._local_user_key_cache: Dict[str, str] = {}
        self._user_locks: Dict[str, threading.RLock] = {}
        self._user_locks_guard = threading.Lock()
        self._bootstrapped_accounts: set[str] = set()

    def _account_id_for_runtime_user(self, safe_user: str) -> str:
        if not safe_user:
            return ""
        if self.client.strong_isolation_enabled:
            return f"{self.client._ACCOUNT_PREFIX}{safe_user}"
        return self.client.shared_account_id

    def _cache_key_for_user(self, user_id: str) -> str:
        runtime_user_id = normalize_user_id(user_id)
        account_id = self._account_id_for_runtime_user(runtime_user_id)
        if not runtime_user_id or not account_id:
            return ""
        return f"{account_id}:{runtime_user_id}"

    def get_user_lock(self, user_id: str) -> threading.RLock:
        cache_key = self._cache_key_for_user(user_id)
        if not cache_key:
            raise RuntimeError("OpenViking user lock requires a non-empty user_id.")
        return self._get_lock_for_cache_key(cache_key)

    def _get_lock_for_cache_key(self, cache_key: str) -> threading.RLock:
        with self._user_locks_guard:
            lock = self._user_locks.get(cache_key)
            if lock is None:
                lock = threading.RLock()
                self._user_locks[cache_key] = lock
            return lock

    def resolve_request_api_key(self, user_id: Optional[str], api_key: Optional[str]) -> str:
        if api_key:
            return api_key.strip()
        if user_id:
            return self.ensure_user_api_key(user_id)
        return self.resolve_system_api_key()

    def resolve_system_api_key(self) -> str:
        key = (self.client.api_key or "").strip()
        if key:
            return key
        return (self.client.root_api_key or "").strip()

    def invalidate_cached_user_key(self, user_id: str) -> None:
        cache_key = self._cache_key_for_user(user_id)
        if cache_key:
            self._local_user_key_cache.pop(cache_key, None)

    def ensure_user_identity(self, user_id: str) -> bool:
        safe_user = normalize_user_id(user_id)
        if not self.client.enabled or not safe_user:
            return False
        try:
            self.ensure_user_api_key(safe_user)
            return True
        except Exception as exc:
            logger.warning("[OpenViking] ensure_user_identity failed user=%s: %s", safe_user, exc)
            return False

    def precreate_users(self, user_ids: Iterable[str]) -> Dict[str, Any]:
        success: List[str] = []
        failed: Dict[str, str] = {}
        total = 0
        for user_id in user_ids:
            candidate = (user_id or "").strip()
            if not candidate:
                continue
            total += 1
            safe_user = normalize_user_id(candidate)
            if not safe_user:
                failed[candidate] = "invalid_user_id"
                continue
            try:
                if self.ensure_user_identity(safe_user):
                    success.append(safe_user)
                else:
                    failed[safe_user] = "ensure_user_identity returned false"
            except Exception as exc:
                failed[safe_user] = str(exc)
        return {
            "requested": total,
            "success": success,
            "failed": failed,
        }

    def ensure_user_api_key(self, user_id: str) -> str:
        safe_user = normalize_user_id(user_id)
        if not safe_user:
            raise RuntimeError("user_id cannot be empty for OpenViking tenant requests.")

        cache_key = self._cache_key_for_user(safe_user)
        key = self._load_cached_user_key(safe_user)
        if key:
            return key

        account_id = self._account_id_for_runtime_user(safe_user)
        lock = self.get_user_lock(safe_user)
        with lock:
            key = self._load_cached_user_key(safe_user)
            if key:
                return key

            self._ensure_account_bootstrapped(account_id)
            register_path = OpenVikingAPI.admin_account_users(account_id)

            try:
                created = self._admin_request(
                    "POST",
                    register_path,
                    json_body={"user_id": safe_user, "role": self.client.account_user_role},
                )
                key = str((created or {}).get("user_key", "")).strip()
            except Exception as exc:
                message = str(exc).upper()
                if "NOT_FOUND" in message and "ACCOUNT" in message:
                    self._bootstrapped_accounts.discard(account_id)
                    self._ensure_account_bootstrapped(account_id)
                    created = self._admin_request(
                        "POST",
                        register_path,
                        json_body={"user_id": safe_user, "role": self.client.account_user_role},
                    )
                    key = str((created or {}).get("user_key", "")).strip()
                elif "ALREADY_EXISTS" in message or "409" in message:
                    key = self._wait_for_cached_user_key(safe_user)
                    if not key:
                        rotated = self._admin_request(
                            "POST",
                            OpenVikingAPI.admin_account_user_key(account_id, safe_user),
                            json_body={},
                        )
                        key = str((rotated or {}).get("user_key", "")).strip()
                else:
                    raise

            if not key:
                raise RuntimeError(
                    f"OpenViking user key is empty for user={safe_user} account={account_id} cache_key={cache_key}."
                )
            self._cache_user_key(safe_user, key)
            return key

    def _admin_request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        allow_not_found: bool = False,
    ) -> Any:
        admin_key = self.resolve_system_api_key()
        if not admin_key:
            raise RuntimeError(
                "OPENVIKING_ROOT_API_KEY or OPENVIKING_API_KEY is required for OpenViking admin calls."
            )
        return self.client._request(
            method,
            path,
            params=params,
            json_body=json_body,
            allow_not_found=allow_not_found,
            api_key=admin_key,
        )

    def _ensure_account_bootstrapped(self, account_id: str) -> None:
        if not account_id:
            raise RuntimeError("OpenViking account_id cannot be empty.")
        if account_id in self._bootstrapped_accounts:
            return

        if not self.client.root_api_key:
            if self.client.strong_isolation_enabled:
                raise RuntimeError(
                    "OPENVIKING_ROOT_API_KEY is required to bootstrap per-user OpenViking accounts."
                )
            # Shared-account mode may use a pre-provisioned admin key. In that case
            # account creation is managed out of band, and user registration will
            # fail fast if the shared account does not actually exist.
            self._bootstrapped_accounts.add(account_id)
            return

        try:
            self.client._request(
                "POST",
                OpenVikingAPI.ADMIN_ACCOUNTS,
                json_body={
                    "account_id": account_id,
                    "admin_user_id": self.client.account_admin_user_id,
                },
                api_key=self.client.root_api_key,
            )
        except Exception as exc:
            message = str(exc).upper()
            if "ALREADY_EXISTS" not in message and "409" not in message:
                raise
        self._bootstrapped_accounts.add(account_id)

    def _load_cached_user_key(self, user_id: str) -> Optional[str]:
        cache_key = self._cache_key_for_user(user_id)
        if not cache_key:
            return None
        return self._local_user_key_cache.get(cache_key)

    def _cache_user_key(self, user_id: str, api_key: str) -> None:
        cache_key = self._cache_key_for_user(user_id)
        key = (api_key or "").strip()
        if not cache_key or not key:
            return
        self._local_user_key_cache[cache_key] = key

    def _wait_for_cached_user_key(self, user_id: str) -> Optional[str]:
        for _ in range(3):
            key = self._load_cached_user_key(user_id)
            if key:
                return key
            time.sleep(0.2)
        return None
