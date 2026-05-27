from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.core.runtime.chat.chat_runtime import ChatRuntime


class RuntimeHook(Protocol):
    order: int

    def run(self, state: "ChatRuntime") -> None:
        ...

