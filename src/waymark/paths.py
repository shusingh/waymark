"""Filesystem paths for local-first Waymark state."""

from __future__ import annotations

import os
from pathlib import Path

from platformdirs import user_data_dir

APP_NAME = "waymark"
APP_AUTHOR = "waymark"
WAYMARK_HOME_ENV = "WAYMARK_HOME"


def waymark_home() -> Path:
    """Return the local Waymark data directory.

    `WAYMARK_HOME` exists for development and tests. Normal users get the
    platform-specific local data directory.
    """

    override = os.environ.get(WAYMARK_HOME_ENV)
    if override:
        return Path(override).expanduser().resolve()

    return Path(user_data_dir(APP_NAME, APP_AUTHOR)).expanduser().resolve()


def ensure_waymark_home() -> Path:
    home = waymark_home()
    home.mkdir(parents=True, exist_ok=True)
    return home


def database_path() -> Path:
    return ensure_waymark_home() / "waymark.sqlite3"


def config_path() -> Path:
    return ensure_waymark_home() / "config.json"
