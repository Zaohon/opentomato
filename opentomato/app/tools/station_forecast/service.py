import json
import os
from typing import Any, Dict, List

import requests

from app.core.config import get_app_settings, is_strict_external_dependencies


def _to_int(value: Any, default: int = 1) -> int:
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except Exception:
        return default


def _compute_summary(points: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not points:
        return {
            "point_count": 0,
            "pv_total": 0.0,
            "load_total": 0.0,
            "peak_pv": {"timestamp": "", "value": 0.0},
            "peak_load": {"timestamp": "", "value": 0.0},
        }

    pv_total = 0.0
    load_total = 0.0
    peak_pv_value = float("-inf")
    peak_pv_ts = ""
    peak_load_value = float("-inf")
    peak_load_ts = ""

    for item in points:
        ts = str(item.get("timestamp", "") or "")
        pv = float(item.get("pvPower", 0.0) or 0.0)
        load = float(item.get("loadPower", 0.0) or 0.0)
        pv_total += pv
        load_total += load
        if pv > peak_pv_value:
            peak_pv_value = pv
            peak_pv_ts = ts
        if load > peak_load_value:
            peak_load_value = load
            peak_load_ts = ts

    return {
        "point_count": len(points),
        "pv_total": round(pv_total, 4),
        "load_total": round(load_total, 4),
        "peak_pv": {"timestamp": peak_pv_ts, "value": round(max(peak_pv_value, 0.0), 4)},
        "peak_load": {"timestamp": peak_load_ts, "value": round(max(peak_load_value, 0.0), 4)},
    }


def get_station_forecast_24h(station_id: int = 1) -> str:
    settings = get_app_settings()
    base_url = (
        os.getenv("FLS_FORECAST_BASE_URL", settings.backend_base_url)
        .strip()
        .rstrip("/")
    )
    timeout = settings.backend_http_timeout_seconds
    safe_station_id = _to_int(station_id, default=_to_int(os.getenv("FLS_FORECAST_DEFAULT_STATION_ID", "1"), 1))
    url = f"{base_url}/v1/forecast/stations/{safe_station_id}"

    headers = {"Accept": "application/json"}
    token = settings.backend_bearer_token
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        payload = resp.json()
        if not isinstance(payload, dict):
            return json.dumps({"station_id": safe_station_id, "raw": payload}, ensure_ascii=False)

        points = payload.get("points", [])
        normalized_points = points if isinstance(points, list) else []
        summary = _compute_summary([p for p in normalized_points if isinstance(p, dict)])
        result = {
            "station_id": safe_station_id,
            "generated_at": payload.get("generatedAt", ""),
            "horizon_hours": payload.get("horizonHours", 24),
            "interval_minutes": payload.get("intervalMinutes", 60),
            "quality_level": payload.get("qualityLevel", ""),
            "summary": summary,
            "points": normalized_points,
        }
        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        if is_strict_external_dependencies():
            return f"Error fetching station forecast: {exc}"
        return f"Error fetching station forecast (non-strict): {exc}"
