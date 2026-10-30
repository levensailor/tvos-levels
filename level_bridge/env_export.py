"""Print shell exports for service startup values loaded from `.env` with python-dotenv.

`scripts/run-service.sh` evaluates this output so `uvicorn --port "${PORT:-8000}"` sees the
`.env` port. Values already present in the environment take precedence over `.env`.
"""

from __future__ import annotations

import os
import shlex
import sys
from collections.abc import Mapping
from pathlib import Path

from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE_VARIABLE = "ENV_FILE"
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
STARTUP_KEYS = ("PORT", "UVICORN_HOST")
PORT_RANGE = (1, 65_535)


def startup_exports(env_file: Path, environ: Mapping[str, str]) -> dict[str, str]:
    file_values = dotenv_values(env_file) if env_file.is_file() else {}
    exports: dict[str, str] = {}
    for key in STARTUP_KEYS:
        if environ.get(key):
            continue
        value = file_values.get(key)
        if value:
            exports[key] = value.strip()
    port = exports.get("PORT", environ.get("PORT"))
    low, high = PORT_RANGE
    if port and (not port.isdigit() or not low <= int(port) <= high):
        raise ValueError(f"PORT must be an integer between {low} and {high}, got {port!r}")
    return exports


def main() -> int:
    env_file = Path(os.environ.get(ENV_FILE_VARIABLE, str(DEFAULT_ENV_FILE)))
    try:
        exports = startup_exports(env_file, os.environ)
    except ValueError as exc:
        print(f"invalid startup configuration: {exc}", file=sys.stderr)
        return 1
    for key, value in exports.items():
        print(f"export {key}={shlex.quote(value)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
