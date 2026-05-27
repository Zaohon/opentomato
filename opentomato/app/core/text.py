from __future__ import annotations


def merge_sections(current: str, extra: str) -> str:
    left = str(current or "").strip()
    right = str(extra or "").strip()
    if not right:
        return left
    if not left:
        return right
    return f"{left}\n{right}"
