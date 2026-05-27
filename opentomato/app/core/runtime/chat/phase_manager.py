from __future__ import annotations

from typing import Dict, List

from app.core.runtime.chat.hooks.base import RuntimeHook
from app.core.runtime.chat.phases import RuntimePhase


class PhaseManager:
    def __init__(self) -> None:
        self._phase_hooks: Dict[RuntimePhase, List[RuntimeHook]] = {
            phase: [] for phase in RuntimePhase
        }

    def add_hook(self, phase: RuntimePhase, hook: RuntimeHook) -> None:
        hooks = self._phase_hooks.setdefault(phase, [])
        hooks.append(hook)
        hooks.sort(key=lambda item: getattr(item, "order", 100))

    def get_hooks(self, phase: RuntimePhase) -> List[RuntimeHook]:
        return list(self._phase_hooks.get(phase, []))
