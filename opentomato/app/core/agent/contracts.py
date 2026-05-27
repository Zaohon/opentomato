import json
import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationError


class AgentFinalResponse(BaseModel):
    kind: Literal["final"] = "final"
    response: str = Field(..., min_length=1)


class AgentHandoffDecision(BaseModel):
    kind: Literal["handoff"] = "handoff"
    target_agent: Literal["control_agent", "analyst_agent", "support_agent"]
    reason: str = Field(..., min_length=1)


def parse_agent_handoff(text: str, *, allowed_targets: list[str]) -> Optional[AgentHandoffDecision]:
    candidate = (text or "").strip()
    if not candidate:
        return None

    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", candidate, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        candidate = fenced.group(1).strip()

    try:
        payload = json.loads(candidate)
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None

    if payload.get("kind") not in {None, "handoff"}:
        return None
    if "target_agent" not in payload:
        return None

    normalized = {
        "kind": "handoff",
        "target_agent": payload.get("target_agent"),
        "reason": payload.get("reason"),
    }
    try:
        if hasattr(AgentHandoffDecision, "model_validate"):
            decision = AgentHandoffDecision.model_validate(normalized)
        else:
            decision = AgentHandoffDecision.parse_obj(normalized)
    except ValidationError:
        return None

    if decision.target_agent not in allowed_targets:
        return None
    return decision
