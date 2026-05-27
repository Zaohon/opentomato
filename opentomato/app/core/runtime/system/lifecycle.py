from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter
from typing import Iterable

from fastapi import FastAPI

from app.core.config import is_strict_external_dependencies, validate_runtime_config
from app.core.config.fls_agent import load_fls_agent_config
from app.core.logging import get_log_timing_enabled
from app.core.runtime.system.bootstrap import (
    init_agents_runtime,
    init_long_term_memory,
    init_resource_library_manager,
    init_short_term_memory,
    init_tools,
    shutdown_runtime,
)
from app.core.runtime.system.health import evaluate_runtime_dependencies


def _log_block(logger, module: str, rows: Iterable[tuple[str, str]]) -> None:
    parts = [f"{k}={v}" for k, v in rows if v is not None and str(v).strip()]
    if not parts:
        logger.info("[启动摘要] 模块=%s", module)
        return
    logger.info("[启动摘要] 模块=%s | %s", module, " | ".join(parts))


def _format_config_lines(agent_cfg: object) -> list[tuple[str, str]]:
    if not isinstance(agent_cfg, dict):
        return [("状态", "缺失")]
    agents = agent_cfg.get("agents", {}) if isinstance(agent_cfg.get("agents", {}), dict) else {}
    return [
        ("version", str(agent_cfg.get("version", "n/a"))),
        ("main_agent", str(agent_cfg.get("main_agent", "n/a"))),
        ("max_hand_off", str(agent_cfg.get("max_hand_off", "n/a"))),
        ("agent_count", str(len(agents))),
        ("strict_external_deps", str(is_strict_external_dependencies())),
    ]


def _format_precreate(precreate: object) -> str:
    data = precreate if isinstance(precreate, dict) else {}
    return (
        f"status={data.get('status', 'unknown')},"
        f"requested={data.get('requested', 0)},"
        f"success={data.get('success', 0)},"
        f"failed={data.get('failed', 0)}"
    )


def _format_readiness_lines(report: dict) -> list[tuple[str, str]]:
    checks = report.get("checks", {}) if isinstance(report.get("checks", {}), dict) else {}
    failed_required: list[str] = []
    for name, result in checks.items():
        if not isinstance(result, dict):
            continue
        if result.get("required", True) and not result.get("ok", False):
            failed_required.append(f"{name}:{result.get('detail', '')}")
    return [
        ("ready", str(report.get("ready", False))),
        ("strict", str(report.get("strict", False))),
        ("failed_required", str(len(failed_required))),
        ("failed_items", ",".join(failed_required) if failed_required else "-"),
    ]


@asynccontextmanager
async def _startup_phase(logger, name: str):
    started = perf_counter()
    if get_log_timing_enabled():
        logger.info("[启动阶段] 名称=%s | 状态=开始", name)
    try:
        yield
        if get_log_timing_enabled():
            elapsed_ms = int((perf_counter() - started) * 1000)
            logger.info("[启动阶段] 名称=%s | 状态=完成 | 耗时毫秒=%d", name, elapsed_ms)
    except Exception:
        if get_log_timing_enabled():
            elapsed_ms = int((perf_counter() - started) * 1000)
            logger.exception("[启动阶段] 名称=%s | 状态=失败 | 耗时毫秒=%d", name, elapsed_ms)
        raise


def _init_souls() -> tuple[int, str]:
    from app.core.agent.soul import SoulManager

    souls_dir = Path(__file__).resolve().parents[3] / "souls"
    SoulManager.initialize(souls_dir)
    return SoulManager.get_souls_count(), SoulManager.get_default_soul_name()


def build_lifespan(logger):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        startup_started = perf_counter()
        if get_log_timing_enabled():
            logger.info("[生命周期] 启动 | 状态=开始")

        agent_cfg = load_fls_agent_config()
        _log_block(logger, "配置", _format_config_lines(agent_cfg if isinstance(agent_cfg, dict) else {}))

        async with _startup_phase(logger, "运行时配置校验"):
            config_errors = validate_runtime_config()
            if config_errors:
                raise RuntimeError("运行时配置无效:\n- " + "\n- ".join(config_errors))

        async with _startup_phase(logger, "长期记忆初始化"):
            memory_status = init_long_term_memory(app)
            _log_block(
                logger,
                "长期记忆",
                [
                    ("enabled", str(memory_status.get("enabled", False))),
                    ("expected_enabled", str(memory_status.get("expected_enabled", False))),
                    ("precreate", _format_precreate(memory_status.get("precreate", {}))),
                ],
            )

        async with _startup_phase(logger, "资源库管理初始化"):
            resource_status = init_resource_library_manager(app)
            _log_block(
                logger,
                "资源库管理",
                [
                    ("enabled", str(resource_status.get("enabled", False))),
                    ("workers", str(resource_status.get("workers", 0))),
                ],
            )

        async with _startup_phase(logger, "工具处理器初始化"):
            tools_status = init_tools(app)
            _log_block(
                logger,
                "工具处理器",
                [
                    ("tool_count", str(tools_status.get("count", 0))),
                ],
            )

        async with _startup_phase(logger, "灵魂配置初始化"):
            souls_count, default_soul = _init_souls()
            _log_block(
                logger,
                "灵魂配置",
                [
                    ("souls_count", str(souls_count)),
                    ("default_soul", default_soul),
                ],
            )

        async with _startup_phase(logger, "Agents初始化"):
            agents_status = init_agents_runtime(app)
            _log_block(
                logger,
                "Agents运行时",
                [
                    ("agents_loaded", str(agents_status.get("agents_loaded", 0))),
                    ("default_agent", str(agents_status.get("default_agent", "n/a"))),
                    ("max_handoffs", str(agents_status.get("max_handoffs", 0))),
                ],
            )

        async with _startup_phase(logger, "短期记忆初始化"):
            session_status = init_short_term_memory(app)
            _log_block(
                logger,
                "短期记忆",
                [
                    ("backend", str(session_status.get("backend", "unknown"))),
                    ("ready", str(session_status.get("ready", False))),
                ],
            )

        async with _startup_phase(logger, "运行时就绪检查"):
            app.state.readiness_report = evaluate_runtime_dependencies(app)
            _log_block(logger, "就绪状态", _format_readiness_lines(app.state.readiness_report))
            if is_strict_external_dependencies() and not app.state.readiness_report["ready"]:
                checks = app.state.readiness_report.get("checks", {})
                failing = [
                    f"{name}:{result.get('detail', '')}"
                    for name, result in checks.items()
                    if isinstance(result, dict) and result.get("required", True) and not result.get("ok", False)
                ]
                raise RuntimeError("严格模式下依赖就绪检查失败:\n- " + "\n- ".join(failing))

        total_ms = int((perf_counter() - startup_started) * 1000)
        _log_block(
            logger,
            "汇总",
            [
                ("startup_ms", str(total_ms)),
                ("agents_loaded", str(agents_status.get("agents_loaded", 0))),
                ("tool_count", str(tools_status.get("count", 0))),
                ("memory_enabled", str(memory_status.get("enabled", False))),
                ("resource_ingest_enabled", str(resource_status.get("enabled", False))),
                ("readiness", str(app.state.readiness_report.get("ready", False))),
            ],
        )
        if get_log_timing_enabled():
            logger.info("[生命周期] 启动 | 状态=完成 | 耗时毫秒=%d", total_ms)

        yield

        shutdown_started = perf_counter()
        if get_log_timing_enabled():
            logger.info("[生命周期] 关闭 | 状态=开始")
        shutdown_runtime(app)
        app.state.readiness_report = {
            "ready": False,
            "strict": is_strict_external_dependencies(),
            "timestamp": None,
            "checks": {},
        }
        if get_log_timing_enabled():
            total_ms = int((perf_counter() - shutdown_started) * 1000)
            logger.info("[生命周期] 关闭 | 状态=完成 | 耗时毫秒=%d", total_ms)

    return lifespan

