import re


_USER_ID_PATTERN = re.compile(r"^\d+$")


def normalize_user_id(user_id: str) -> str:
    """
    Normalize and validate external user_id.

    Rules:
    - non-empty after strip
    - one or more digits (e.g. 1, 2, 11, 123, 10001)
    """
    candidate = (user_id or "").strip()
    if not candidate:
        raise ValueError("user_id is required.")
    if not _USER_ID_PATTERN.fullmatch(candidate):
        raise ValueError(
            "user_id must match ^\\d+$ (digits only)."
        )
    return candidate
