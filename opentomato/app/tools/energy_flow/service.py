import json
import os

import requests

from app.core.config import get_app_settings, is_strict_external_dependencies


def get_energy_flow(user_id: str = "default_user") -> str:
    settings = get_app_settings()
    base_url = (
        os.getenv("FLS_ENERGY_FLOW_BASE_URL", settings.backend_base_url)
        .strip()
        .rstrip("/")
    )
    timeout = settings.backend_http_timeout_seconds
    headers = {"Accept": "application/json"}
    token = settings.backend_bearer_token
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        safe_user = (user_id or "default_user").strip()
        resp = requests.get(
            f"{base_url}/v1/energy/user/{safe_user}/live",
            headers=headers,
            timeout=timeout,
        )
        resp.raise_for_status()
        payload = resp.json()
        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, dict):
                if safe_user in data:
                    return json.dumps(
                        {
                            "code": payload.get("code", 200),
                            "message": payload.get("message", "success"),
                            "timestamp": payload.get("timestamp"),
                            "data": {safe_user: data.get(safe_user)},
                        },
                        ensure_ascii=False,
                    )
                if data:
                    first_key = next(iter(data.keys()))
                    return json.dumps(
                        {
                            "code": payload.get("code", 200),
                            "message": payload.get("message", "success"),
                            "timestamp": payload.get("timestamp"),
                            "data": {first_key: data.get(first_key)},
                        },
                        ensure_ascii=False,
                    )
        return payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    except Exception as exc:
        if is_strict_external_dependencies():
            return f"Error fetching energy flow: {exc}"
        return f"Error fetching energy flow (non-strict): {exc}"
