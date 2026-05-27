from __future__ import annotations

import builtins
import logging
import logging.config
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from uvicorn.logging import AccessFormatter, DefaultFormatter
from app.core.config.bools import read_bool_env

_VALID_LOG_OUTPUTS = {"k8s", "file", "both"}
_VALID_LOG_LANGUAGES = {"cn", "en"}
_PRINT_REDIRECT_INSTALLED = False
_LOGGING_CONFIGURED = False
_BRIDGE_LOGGER = logging.getLogger("app.print")
_DEFAULT_LOG_TIMEZONE = "Asia/Shanghai"

_APP_DIR = Path(__file__).resolve().parents[2]
_DEFAULT_LOGS_DIR = _APP_DIR / "logs"
_FLS_AGENT_CONFIG_PATH = _APP_DIR / "fls_agent.yaml"
_CN_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bWarning:\s*"), "警告: "),
    (re.compile(r"\bwarning\b", re.IGNORECASE), "警告"),
    (re.compile(r"\bConnected to\b"), "已连接到"),
    (re.compile(r"\bConnected successfully as\b"), "已成功连接，客户端 ID 为"),
    (re.compile(r"\bConnecting to\b"), "正在连接到"),
    (re.compile(r"\bConnection failed\b"), "连接失败"),
    (re.compile(r"\bConnection lost during init\b"), "初始化期间连接中断"),
    (re.compile(r"\bConnection lost during query\b"), "查询期间连接中断"),
    (re.compile(r"\bConnection lost during update\b"), "更新期间连接中断"),
    (re.compile(r"\bReconnected successfully\b"), "重连成功"),
    (re.compile(r"\bRetry failed\b"), "重试失败"),
    (re.compile(r"\bFailed to initialize client\b"), "初始化客户端失败"),
    (re.compile(r"\bFailed to initialize InfluxDB client\b"), "初始化 InfluxDB 客户端失败"),
    (re.compile(r"\bFailed to load\b"), "加载失败"),
    (re.compile(r"\bFailed to fetch\b"), "获取失败"),
    (re.compile(r"\bFailed to resolve\b"), "解析失败"),
    (re.compile(r"\bFailed to schedule\b"), "调度失败"),
    (re.compile(r"\bFailed to cancel\b"), "取消失败"),
    (re.compile(r"\bFailed to release\b"), "释放失败"),
    (re.compile(r"\bFailed to record\b"), "记录失败"),
    (re.compile(r"\bFailed to commit\b"), "提交失败"),
    (re.compile(r"\bFailed to call\b"), "调用失败"),
    (re.compile(r"\bFailed to\b"), "失败: "),
    (re.compile(r"\bQuery failed\b"), "查询失败"),
    (re.compile(r"\bPublish error\b"), "发布错误"),
    (re.compile(r"\bPublish timeout\b"), "发布超时"),
    (re.compile(r"\bMissing\b"), "缺少"),
    (re.compile(r"\bskipped\b", re.IGNORECASE), "已跳过"),
    (re.compile(r"\bdone\b", re.IGNORECASE), "完成"),
    (re.compile(r"\bsucceeded\b", re.IGNORECASE), "成功"),
    (re.compile(r"\bsuccessfully\b", re.IGNORECASE), "成功"),
    (re.compile(r"\bdisabled\b", re.IGNORECASE), "已禁用"),
    (re.compile(r"\benabled=false\b", re.IGNORECASE), "enabled=false"),
    (re.compile(r"\bReturning mock data\b"), "返回模拟数据"),
    (re.compile(r"\bReturning mock telemetry\b"), "返回模拟遥测数据"),
    (re.compile(r"\bUsing mock\b"), "使用模拟数据"),
    (re.compile(r"\bfallback to memory backend\b", re.IGNORECASE), "回退到内存后端"),
    (re.compile(r"\bfallback to memory\b", re.IGNORECASE), "回退到内存"),
    (re.compile(r"\bfallback to generate\b", re.IGNORECASE), "回退到生成逻辑"),
    (re.compile(r"\bService Started\b"), "服务已启动"),
    (re.compile(r"\bService Stopped\b"), "服务已停止"),
    (re.compile(r"\bStarted with\b"), "已启动，worker 数"),
    (re.compile(r"\bGoodbye\b"), "已退出"),
    (re.compile(r"\bPlease set it in a \.env file\b"), "请在 .env 文件中设置"),
    (re.compile(r"\bPlease provide a question\b"), "请提供一个问题"),
    (re.compile(r"\bAction executed\b"), "动作已执行"),
    (re.compile(r"\bUsing Aliyun PAI forecast for\b"), "正在为以下用户使用阿里云 PAI 预测"),
    (re.compile(r"\bRemote PAI failed\b"), "远程 PAI 调用失败"),
    (re.compile(r"\bOpen-Meteo API error\b"), "Open-Meteo API 错误"),
    (re.compile(r"\bOpen-Meteo hourly unavailable\b"), "Open-Meteo 小时级数据不可用"),
    (re.compile(r"\bSuccessfully wrote\b"), "成功写入"),
    (re.compile(r"\bSyncing forecast for\b"), "正在同步预测，用户"),
    (re.compile(r"\bTriggering forecast task for\b"), "正在触发预测任务，用户"),
    (re.compile(r"\bTriggering scheduled task\b"), "正在触发定时任务"),
    (re.compile(r"\bExecution Result\b"), "执行结果"),
    (re.compile(r"\bExecution Failed\b"), "执行失败"),
    (re.compile(r"\bstartup\b"), "启动"),
    (re.compile(r"\blifespan startup\b"), "生命周期启动"),
    (re.compile(r"\blifespan shutdown\b"), "生命周期关闭"),
    (re.compile(r"\bphase\b"), "阶段"),
    (re.compile(r"\bstatus=start\b"), "状态=开始"),
    (re.compile(r"\bstatus=ok\b"), "状态=成功"),
    (re.compile(r"\bstatus=fail\b"), "状态=失败"),
    (re.compile(r"\bstatus=degraded\b"), "状态=降级"),
    (re.compile(r"\bduration_ms\b"), "耗时毫秒"),
    (re.compile(r"\blogging configured\b"), "日志系统已配置"),
    (re.compile(r"\boutput\b"), "输出"),
    (re.compile(r"\blogs_dir\b"), "日志目录"),
    (re.compile(r"\bfile\b"), "文件"),
]


def _read_bool(name: str, default: bool) -> bool:
    return read_bool_env(name, default=default)


def get_log_output_mode() -> str:
    """
    Resolve log output mode.
    - k8s: stdout/stderr only
    - file: rotating files only
    - both: stdout/stderr and rotating files
    """
    raw = os.getenv("LOG_OUTPUT", "both").strip().lower()
    if raw in _VALID_LOG_OUTPUTS:
        return raw
    return "both"


def get_log_language() -> str:
    raw = os.getenv("LOG_LANGUAGE", "cn").strip().lower()
    if raw in _VALID_LOG_LANGUAGES:
        return raw
    return "cn"


def get_log_timing_enabled() -> bool:
    return _read_bool("LOG_TIMING_ENABLED", default=False)


def _translate_to_cn(message: str) -> str:
    translated = message
    for pattern, replacement in _CN_REPLACEMENTS:
        translated = pattern.sub(replacement, translated)
    return translated


def localize_log_message(message: str) -> str:
    if not message:
        return message
    if get_log_language() == "en":
        return message
    return _translate_to_cn(message)


class LocalizedLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            localized = localize_log_message(record.getMessage())
            record.msg = localized
            record.args = ()
        except Exception:
            return True
        return True


class HttpxDebugFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno == logging.INFO:
            record.levelno = logging.DEBUG
            record.levelname = "DEBUG"
        return True


def get_log_timezone() -> str:
    raw = os.getenv("LOG_TIMEZONE", _DEFAULT_LOG_TIMEZONE).strip()
    return raw or _DEFAULT_LOG_TIMEZONE


def _resolve_log_timezone() -> ZoneInfo:
    try:
        return ZoneInfo(get_log_timezone())
    except Exception:
        return ZoneInfo(_DEFAULT_LOG_TIMEZONE)


class ReadableFormatter(logging.Formatter):
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        dt = datetime.fromtimestamp(record.created, _resolve_log_timezone())
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S")


class ReadableDefaultFormatter(DefaultFormatter):
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        dt = datetime.fromtimestamp(record.created, _resolve_log_timezone())
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S")


class ReadableAccessFormatter(AccessFormatter):
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        dt = datetime.fromtimestamp(record.created, _resolve_log_timezone())
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S")


def _read_logs_dir_from_config() -> str:
    """
    Read logs_dir from app/fls_agent.yaml.
    Returns empty string when unavailable to keep logging bootstrap resilient.
    """
    if not _FLS_AGENT_CONFIG_PATH.exists():
        return ""
    try:
        import yaml

        data = yaml.safe_load(_FLS_AGENT_CONFIG_PATH.read_text(encoding="utf-8")) or {}
        if isinstance(data, dict):
            raw = data.get("logs_dir", "")
            if isinstance(raw, str):
                return raw.strip()
    except Exception:
        return ""
    return ""


def _read_log_level_from_config() -> str:
    if not _FLS_AGENT_CONFIG_PATH.exists():
        return ""
    try:
        import yaml

        data = yaml.safe_load(_FLS_AGENT_CONFIG_PATH.read_text(encoding="utf-8")) or {}
        if isinstance(data, dict):
            raw = data.get("loging_level", data.get("logging_level", ""))
            if isinstance(raw, str):
                return raw.strip().upper()
    except Exception:
        return ""
    return ""


def resolve_logs_dir() -> Path:
    """
    Resolve logs directory:
    1) app/fls_agent.yaml: logs_dir
    2) default app/logs
    """
    configured = _read_logs_dir_from_config()
    if configured:
        candidate = Path(configured)
        if not candidate.is_absolute():
            candidate = _APP_DIR / candidate
    else:
        candidate = _DEFAULT_LOGS_DIR

    candidate.mkdir(parents=True, exist_ok=True)
    return candidate


def _include_stdout() -> bool:
    return get_log_output_mode() in {"k8s", "both"}


def _include_file() -> bool:
    return get_log_output_mode() in {"file", "both"}


def build_uvicorn_log_config() -> dict:
    output_mode = get_log_output_mode()
    logs_dir = resolve_logs_dir() if _include_file() else None
    access_log_file = logs_dir / "uvicorn_access.log" if logs_dir else None
    error_log_file = logs_dir / "uvicorn_error.log" if logs_dir else None

    handlers: dict[str, dict] = {}
    uvicorn_handlers: list[str] = []
    uvicorn_access_handlers: list[str] = []

    if _include_stdout():
        handlers["default"] = {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "filters": ["localized"],
        }
        handlers["access"] = {
            "formatter": "access",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        }
        uvicorn_handlers.append("default")
        uvicorn_access_handlers.append("access")

    if _include_file() and error_log_file and access_log_file:
        handlers["uvicorn_error_file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "default",
            "filename": str(error_log_file),
            "maxBytes": int(os.getenv("LOG_FILE_MAX_BYTES", "10485760")),
            "backupCount": int(os.getenv("LOG_FILE_BACKUP_COUNT", "5")),
            "encoding": "utf-8",
            "filters": ["localized"],
        }
        handlers["uvicorn_access_file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "access",
            "filename": str(access_log_file),
            "maxBytes": int(os.getenv("LOG_FILE_MAX_BYTES", "10485760")),
            "backupCount": int(os.getenv("LOG_FILE_BACKUP_COUNT", "5")),
            "encoding": "utf-8",
        }
        uvicorn_handlers.append("uvicorn_error_file")
        uvicorn_access_handlers.append("uvicorn_access_file")

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "localized": {
                "()": "app.core.logging.bootstrap.LocalizedLogFilter",
            },
            "httpx_debug": {
                "()": "app.core.logging.bootstrap.HttpxDebugFilter",
            }
        },
        "formatters": {
            "default": {
                "()": "app.core.logging.bootstrap.ReadableDefaultFormatter",
                "fmt": "%(asctime)s | %(levelprefix)s | %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
                "use_colors": False,
            },
            "access": {
                "()": "app.core.logging.bootstrap.ReadableAccessFormatter",
                "fmt": "%(asctime)s | %(levelprefix)s | %(client_addr)s - \"%(request_line)s\" %(status_code)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
                "use_colors": False,
            },
        },
        "handlers": handlers,
        "loggers": {
            "uvicorn": {
                "handlers": uvicorn_handlers,
                "level": os.getenv("UVICORN_LOG_LEVEL", "INFO").upper(),
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": uvicorn_handlers,
                "level": os.getenv("UVICORN_LOG_LEVEL", "INFO").upper(),
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": uvicorn_access_handlers,
                "level": os.getenv("UVICORN_ACCESS_LOG_LEVEL", "WARNING").upper(),
                "propagate": False,
            },
            "httpcore": {
                "level": os.getenv("HTTPCORE_LOG_LEVEL", "WARNING").upper(),
                "propagate": True,
            },
            "httpx": {
                "level": os.getenv("HTTPX_LOG_LEVEL", "WARNING").upper(),
                "filters": ["httpx_debug"],
                "propagate": True,
            },
            "openai": {
                "level": os.getenv("OPENAI_LOG_LEVEL", "WARNING").upper(),
                "propagate": True,
            },
            "openai._base_client": {
                "level": os.getenv("OPENAI_BASE_CLIENT_LOG_LEVEL", os.getenv("OPENAI_LOG_LEVEL", "WARNING")).upper(),
                "propagate": False,
            },
        },
    }


def configure_app_logging() -> None:
    """
    Configure a process-wide logging baseline for app logs.
    Uvicorn may later apply its own log config; this function stays idempotent.
    """
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    output_mode = get_log_output_mode()
    language = get_log_language()
    timezone_name = get_log_timezone()
    logs_dir = resolve_logs_dir() if _include_file() else None
    app_log_file = logs_dir / "app.log" if logs_dir else None

    configured_level = _read_log_level_from_config()
    level_name = (os.getenv("LOG_LEVEL", "").strip() or configured_level or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    handlers: dict[str, dict] = {}
    root_handlers: list[str] = []

    if _include_stdout():
        handlers["stdout"] = {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stdout",
            "filters": ["localized"],
        }
        root_handlers.append("stdout")

    if _include_file() and app_log_file:
        handlers["app_file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "default",
            "filename": str(app_log_file),
            "maxBytes": int(os.getenv("LOG_FILE_MAX_BYTES", "10485760")),
            "backupCount": int(os.getenv("LOG_FILE_BACKUP_COUNT", "5")),
            "encoding": "utf-8",
            "filters": ["localized"],
        }
        root_handlers.append("app_file")

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "localized": {
                    "()": "app.core.logging.bootstrap.LocalizedLogFilter",
                },
                "httpx_debug": {
                    "()": "app.core.logging.bootstrap.HttpxDebugFilter",
                }
            },
            "formatters": {
                "default": {
                    "()": "app.core.logging.bootstrap.ReadableFormatter",
                    "format": "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                }
            },
            "handlers": handlers,
            "root": {"level": level, "handlers": root_handlers},
            "loggers": {
                "httpcore": {
                    "level": os.getenv("HTTPCORE_LOG_LEVEL", "WARNING").upper(),
                    "propagate": True,
                },
                "httpx": {
                    "level": os.getenv("HTTPX_LOG_LEVEL", "WARNING").upper(),
                    "filters": ["httpx_debug"],
                    "propagate": True,
                },
                "openai": {
                    "level": os.getenv("OPENAI_LOG_LEVEL", "WARNING").upper(),
                    "propagate": True,
                },
                "openai._base_client": {
                    "level": os.getenv("OPENAI_BASE_CLIENT_LOG_LEVEL", os.getenv("OPENAI_LOG_LEVEL", "WARNING")).upper(),
                    "propagate": False,
                },
            },
        }
    )
    _LOGGING_CONFIGURED = True
    _BRIDGE_LOGGER.info(
        "logging configured output=%s language=%s timezone=%s logs_dir=%s file=%s",
        output_mode,
        language,
        timezone_name,
        logs_dir or "",
        app_log_file or "",
    )


def install_print_logging_bridge() -> None:
    """
    Redirect built-in print to logging so legacy print statements flow through the unified logger.
    Enable/disable via LOG_PRINT_REDIRECT_ENABLED (default true).
    """
    global _PRINT_REDIRECT_INSTALLED
    if _PRINT_REDIRECT_INSTALLED:
        return
    if not _read_bool("LOG_PRINT_REDIRECT_ENABLED", default=True):
        return

    def _logging_print(*args, **kwargs):
        sep = kwargs.get("sep", " ")
        end = kwargs.get("end", "\n")
        message = sep.join(str(a) for a in args)
        if end and end != "\n":
            message = f"{message}{end}"
        if not message:
            return
        _BRIDGE_LOGGER.info(message)

    builtins.print = _logging_print
    _PRINT_REDIRECT_INSTALLED = True


