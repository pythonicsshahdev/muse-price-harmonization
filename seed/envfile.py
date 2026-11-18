"""Read the workspace .env without printing or exporting any value.

Values come from the file first, then os.environ overrides them. ENV_FILE points the
loader at another file (the tests use this so they never read real credentials).
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict

DEFAULT_ENV = Path(__file__).resolve().parent.parent / ".env"


class MissingConfig(RuntimeError):
    """A required .env key is absent or blank."""


def load_env() -> Dict[str, str]:
    path = Path(os.environ.get("ENV_FILE") or DEFAULT_ENV)
    env: Dict[str, str] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = re.sub(r"\s+#.*$", "", value).strip().strip('"').strip("'")
            env[key.strip()] = value
    for key, value in os.environ.items():
        if value:
            env[key] = value
    return env


def require(env: Dict[str, str], key: str) -> str:
    value = env.get(key, "")
    if not value:
        raise MissingConfig("Missing required .env key: %s" % key)
    return value
