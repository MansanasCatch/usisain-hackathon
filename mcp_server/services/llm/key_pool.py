"""key_pool.py — runtime-reloadable API key pool shared by the cloud LLM
providers (Gemini, Grok).

Keys are read from an environment variable on every access, so changing
them at runtime (via the dashboard's AI Settings panel, which updates both
``os.environ`` and ``.env``) takes effect on the very next request — no
backend restart required.

Supports a single key or a comma-separated list for round-robin rotation:

    GEMINI_API_KEY=key1,key2,key3
"""

import os
import threading


def parse_keys(raw: str | None) -> list[str]:
    """Split a comma-separated key string into a clean, ordered list."""
    return [k.strip() for k in (raw or "").split(",") if k.strip()]


def mask_key(key: str | None) -> str:
    """Return a safe, non-reversible hint for displaying a key in the UI/logs."""
    if not key:
        return ""
    if len(key) <= 8:
        return "•" * len(key)
    return f"{key[:4]}…{key[-4:]}"


class KeyPool:
    """Thread-safe round-robin pool that re-parses its env var whenever the
    underlying value changes."""

    def __init__(self, env_var: str):
        self.env_var = env_var
        self._raw: str | None = None
        self._keys: list[str] = []
        self._index = 0
        self._lock = threading.Lock()

    def _refresh_locked(self) -> None:
        raw = os.environ.get(self.env_var, "")
        if raw != self._raw:
            self._raw = raw
            self._keys = parse_keys(raw)
            self._index = 0

    def keys(self) -> list[str]:
        with self._lock:
            self._refresh_locked()
            return list(self._keys)

    def has_keys(self) -> bool:
        return bool(self.keys())

    def next_key(self) -> str | None:
        """Return the next key in round-robin order, or None if empty."""
        with self._lock:
            self._refresh_locked()
            if not self._keys:
                return None
            key = self._keys[self._index % len(self._keys)]
            self._index = (self._index + 1) % len(self._keys)
            return key
