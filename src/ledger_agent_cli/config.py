from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any

_SENTINEL = object()


@lru_cache
def get_config() -> dict[str, Any]:
    """Load and return the parsed TOML config.

    The result is cached for the lifetime of the process via ``@lru_cache``.
    Tests that switch working directories should call ``clear_config_cache()``
    to ensure the config is re-read from the new location.
    """
    path = find_config_file()
    if path is None:
        return {}
    return tomllib.loads(path.read_text(encoding="utf-8"))


def find_config_file() -> Path | None:
    candidates = [".ledger-cli.toml", "ledger-cli.toml"]

    current = Path.cwd().resolve()
    for directory in [current, *current.parents]:
        for name in candidates:
            path = directory / name
            if path.exists():
                return path
        if (directory / ".git").exists():
            break

    home = Path.home()
    for name in candidates:
        path = home / name
        if path.exists():
            return path

    return None


def get_default(key_path: list[str], fallback: Any | None = None) -> Any:
    config = get_config()
    for key in key_path:
        if not isinstance(config, dict):
            return fallback
        value = config.get(key, _SENTINEL)
        if value is _SENTINEL:
            return fallback
        config = value
    return config


def clear_config_cache() -> None:
    get_config.cache_clear()
