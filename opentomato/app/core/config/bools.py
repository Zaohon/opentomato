import os


_TRUE_VALUES = {"1", "true", "yes", "on"}


def read_bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUE_VALUES
