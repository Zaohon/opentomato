from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

import yaml

from app.core.logging import get_logger


APP_DIR = Path(__file__).resolve().parents[2]
FLS_AGENT_CONFIG_PATH = APP_DIR / "fls_agent.yaml"
logger = get_logger("app.config.fls_agent")


@dataclass(frozen=True)
class AgentExecutionSpec:
    response_mode: str = "normal"
    default_handoff: str = "support_agent"
    bind_tools: bool = True
    bind_memory: bool = True
    initial_tool_choice: str = "auto"


@dataclass(frozen=True)
class AgentSpec:
    logical_name: str
    definition: str
    skills: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    allowed_handoff: List[str] = field(default_factory=list)
    default_model: str = "qwen-plus"
    execution: AgentExecutionSpec = field(default_factory=AgentExecutionSpec)

    @property
    def agent_dir(self) -> Path:
        return APP_DIR / "agents" / self.definition


@dataclass(frozen=True)
class AgentRegistry:
    version: int
    main_agent: str
    max_handoffs: int
    skills_dir: Path
    raw_config: Dict[str, Any]
    agents: Dict[str, AgentSpec]


def _normalize_string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    normalized: List[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            normalized.append(item.strip())
    return normalized


def _read_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


@lru_cache(maxsize=1)
def load_fls_agent_config() -> Dict[str, Any]:
    if not FLS_AGENT_CONFIG_PATH.exists():
        return {}
    try:
        data = yaml.safe_load(FLS_AGENT_CONFIG_PATH.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning("[AgentConfig] load_failed path=app/fls_agent.yaml error=%s", exc)
        return {}


def _parse_agent_spec(logical_name: str, spec: Dict[str, Any]) -> AgentSpec:
    definition = str(spec.get("definition", logical_name)).strip() or logical_name
    execution_raw = spec.get("execution") if isinstance(spec.get("execution"), dict) else {}
    execution = AgentExecutionSpec(
        response_mode=str(execution_raw.get("response_mode", "normal")).strip().lower() or "normal",
        default_handoff=str(execution_raw.get("default_handoff", "support_agent")).strip() or "support_agent",
        bind_tools=_read_bool(execution_raw.get("bind_tools"), default=True),
        bind_memory=_read_bool(execution_raw.get("bind_memory"), default=True),
        initial_tool_choice=str(execution_raw.get("initial_tool_choice", "auto")).strip().lower() or "auto",
    )
    return AgentSpec(
        logical_name=logical_name,
        definition=definition,
        skills=_normalize_string_list(spec.get("skills")),
        tools=_normalize_string_list(spec.get("tools")),
        allowed_handoff=_normalize_string_list(spec.get("allowed_handoff")),
        default_model=str(spec.get("default_model", "qwen-plus")).strip() or "qwen-plus",
        execution=execution,
    )


@lru_cache(maxsize=1)
def load_agent_registry() -> AgentRegistry:
    raw = load_fls_agent_config()
    raw_agents = raw.get("agents", {}) if isinstance(raw.get("agents"), dict) else {}
    agents: Dict[str, AgentSpec] = {}
    for logical_name, spec in raw_agents.items():
        if not isinstance(spec, dict):
            continue
        agents[logical_name] = _parse_agent_spec(logical_name, spec)

    skills_dir_raw = raw.get("skills_dir", "skills")
    if not isinstance(skills_dir_raw, str) or not skills_dir_raw.strip():
        skills_dir_raw = "skills"
    skills_dir = Path(skills_dir_raw.strip())
    if not skills_dir.is_absolute():
        skills_dir = APP_DIR / skills_dir

    max_handoffs_raw = raw.get("max_hand_off", raw.get("max_handoffs", 1))
    try:
        max_handoffs = max(int(max_handoffs_raw), 0)
    except Exception:
        max_handoffs = 1

    version_raw = raw.get("version", 1)
    try:
        version = int(version_raw)
    except Exception:
        version = 1

    main_agent = str(raw.get("main_agent", "router")).strip() or "router"

    return AgentRegistry(
        version=version,
        main_agent=main_agent,
        max_handoffs=max_handoffs,
        skills_dir=skills_dir,
        raw_config=raw,
        agents=agents,
    )


def get_skills_dir() -> Path:
    return load_agent_registry().skills_dir
