"""Persistent launcher preferences (e.g. "Don't ask again")."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class LauncherConfig:
    dont_ask_again: bool = False
    last_browser: str | None = None

    @classmethod
    def load(cls, path: Path) -> LauncherConfig:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return cls()
        except (OSError, ValueError) as exc:
            log.warning("Ignoring unreadable config %s: %s", path, exc)
            return cls()
        if not isinstance(raw, dict):
            return cls()
        last = raw.get("last_browser")
        return cls(
            dont_ask_again=bool(raw.get("dont_ask_again", False)),
            last_browser=last if isinstance(last, str) else None,
        )

    def save(self, path: Path) -> bool:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
            tmp.replace(path)
            return True
        except OSError as exc:
            log.error("Could not save config %s: %s", path, exc)
            return False


def should_prompt(config: LauncherConfig, installed: bool | None) -> bool:
    """Prompt unless the user opted out or the extension is known to be installed."""
    if config.dont_ask_again:
        return False
    return installed is not True
