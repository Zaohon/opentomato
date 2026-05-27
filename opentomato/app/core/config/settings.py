import os
from dataclasses import dataclass
from functools import lru_cache
from typing import List

from dotenv import load_dotenv
from app.core.config.bools import read_bool_env

# Load environment variables once at process startup.
load_dotenv()

_PRODUCTION_ENVS = {"prod", "production"}
_TRUE_VALUES = {"1", "true", "yes", "on"}


def _looks_like_placeholder(value: str) -> bool:
    v = value.strip().lower()
    if not v:
        return True
    if v.startswith("your_"):
        return True
    if "example" in v:
        return True
    if "changeme" in v or "change_me" in v:
        return True
    if v in {"my-token", "my-org", "root"}:
        return True
    return False


@dataclass(frozen=True)
class AppSettings:
    app_env: str
    strict_external_dependencies: bool
    cors_allow_origins: List[str]
    memory_debug_api_enabled: bool
    backend_base_url: str
    backend_http_timeout_seconds: float
    backend_bearer_token: str
    mqtt_device_id_template: str
    safety_guard_mode: str
    llm_api_key: str
    llm_base_url: str
    profile_model: str


@lru_cache(maxsize=1)
def get_app_settings() -> AppSettings:
    app_env = os.getenv("APP_ENV", "development").strip().lower()
    is_prod = app_env in _PRODUCTION_ENVS
    strict_external_dependencies = read_bool_env("STRICT_EXTERNAL_DEPENDENCIES", default=is_prod)
    raw_cors = os.getenv("CORS_ALLOW_ORIGINS", "*")
    cors_allow_origins = [item.strip() for item in raw_cors.split(",") if item.strip()] or ["*"]
    raw_memory_debug = os.getenv("MEMORY_DEBUG_API_ENABLED")
    if raw_memory_debug is not None:
        memory_debug_api_enabled = raw_memory_debug.strip().lower() in _TRUE_VALUES
    else:
        memory_debug_api_enabled = app_env != "production"

    return AppSettings(
        app_env=app_env,
        strict_external_dependencies=strict_external_dependencies,
        cors_allow_origins=cors_allow_origins,
        memory_debug_api_enabled=memory_debug_api_enabled,
        backend_base_url=os.getenv("FLS_BACKEND_BASE_URL", "https://api.felicitysolar-shanghai.com/api").strip().rstrip("/"),
        backend_http_timeout_seconds=float(os.getenv("BACKEND_HTTP_TIMEOUT_SECONDS", "8")),
        backend_bearer_token=os.getenv("FLS_BACKEND_BEARER_TOKEN", "").strip(),
        mqtt_device_id_template=os.getenv("MQTT_DEVICE_ID_TEMPLATE", "dev_{user_id}").strip(),
        safety_guard_mode=os.getenv("SAFETY_GUARD_MODE", "strict").strip().lower(),
        llm_api_key=os.getenv("DASHSCOPE_API_KEY", "").strip(),
        llm_base_url=os.getenv("OPENAI_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1").strip(),
        profile_model=(
            os.getenv("PROFILE_MODEL", "")
            or "qwen3.6-plus"
        ).strip(),
    )


def is_strict_external_dependencies() -> bool:
    return get_app_settings().strict_external_dependencies


def get_cors_allow_origins() -> List[str]:
    return list(get_app_settings().cors_allow_origins)


def _validate_required_key(errors: List[str], key: str) -> None:
    value = os.getenv(key, "").strip()
    if not value:
        errors.append(f"{key} is required.")
        return
    if _looks_like_placeholder(value):
        errors.append(f"{key} is missing or uses a placeholder value.")


def validate_runtime_config() -> List[str]:
    errors: List[str] = []
    settings = get_app_settings()

    if not settings.llm_api_key:
        errors.append("Missing LLM credential: set DASHSCOPE_API_KEY.")

    if read_bool_env("OPENVIKING_ENABLED", default=True):
        _validate_required_key(errors, "OPENVIKING_URL")
        if read_bool_env("OPENVIKING_STRONG_ISOLATION", default=True):
            _validate_required_key(errors, "OPENVIKING_ROOT_API_KEY")
        else:
            shared_key = os.getenv("OPENVIKING_API_KEY", "").strip()
            root_key = os.getenv("OPENVIKING_ROOT_API_KEY", "").strip()
            if not shared_key and not root_key:
                errors.append(
                    "OPENVIKING_API_KEY or OPENVIKING_ROOT_API_KEY is required when OPENVIKING_STRONG_ISOLATION=false."
                )
            elif shared_key and _looks_like_placeholder(shared_key):
                errors.append("OPENVIKING_API_KEY is missing or uses a placeholder value.")
            elif root_key and _looks_like_placeholder(root_key):
                errors.append("OPENVIKING_ROOT_API_KEY is missing or uses a placeholder value.")

    if settings.app_env not in _PRODUCTION_ENVS:
        return errors

    if settings.cors_allow_origins == ["*"]:
        errors.append("CORS_ALLOW_ORIGINS cannot be '*' in production.")

    optional_sensitive = {
        "DASHSCOPE_API_KEY": os.getenv("DASHSCOPE_API_KEY", "").strip(),
        "OPENVIKING_API_KEY": os.getenv("OPENVIKING_API_KEY", "").strip(),
        "OPENVIKING_ROOT_API_KEY": os.getenv("OPENVIKING_ROOT_API_KEY", "").strip(),
        "SECRET_KEY": os.getenv("SECRET_KEY", "").strip(),
        "ACCESS_KEY": os.getenv("ACCESS_KEY", "").strip(),
    }
    for key, value in optional_sensitive.items():
        if value and _looks_like_placeholder(value):
            errors.append(f"{key} appears to be a placeholder.")

    return errors

