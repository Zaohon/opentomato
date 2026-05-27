from __future__ import annotations

import logging
from time import perf_counter
from typing import Any

from .bootstrap import (
    build_uvicorn_log_config,
    configure_app_logging,
    get_log_language,
    get_log_output_mode,
    get_log_timing_enabled,
    install_print_logging_bridge,
    localize_log_message,
)


class AppLogger:
    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(name)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.warning(msg, *args, **kwargs)

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.exception(msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.error(msg, *args, **kwargs)

    def setLevel(self, level: str | int) -> None:
        self._logger.setLevel(level)

    def isEnabledFor(self, level: int) -> bool:
        return self._logger.isEnabledFor(level)

    @property
    def raw(self) -> logging.Logger:
        return self._logger


def get_logger(name: str) -> AppLogger:
    return AppLogger(name)


class LogTimer:
    def __init__(self, logger: AppLogger, name: str, **fields: Any) -> None:
        self.logger = logger
        self.name = name
        self.fields = dict(fields)
        self.started = 0.0

    def __enter__(self) -> "LogTimer":
        self.started = perf_counter()
        return self

    def __exit__(self, _exc_type, exc, _tb) -> bool:
        if not get_log_timing_enabled():
            return False
        duration_ms = int((perf_counter() - self.started) * 1000)
        suffix = " ".join(f"{key}={value}" for key, value in self.fields.items() if value not in {"", None})
        status = "失败" if exc is not None else "成功"
        message = f"[耗时] 名称={self.name} 状态={status} 总耗时：={duration_ms}毫秒"
        if suffix:
            message = f"{message} {suffix}"
        if exc is not None:
            self.logger.warning(message)
        else:
            self.logger.info(message)
        return False


def log_timing(logger: AppLogger, name: str, **fields: Any) -> LogTimer:
    return LogTimer(logger, name, **fields)


__all__ = [
    "AppLogger",
    "get_logger",
    "log_timing",
    "build_uvicorn_log_config",
    "configure_app_logging",
    "get_log_language",
    "get_log_output_mode",
    "get_log_timing_enabled",
    "install_print_logging_bridge",
    "localize_log_message",
]
