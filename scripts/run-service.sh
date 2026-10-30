#!/usr/bin/env bash
# Starts the bridge with PORT/UVICORN_HOST loaded from .env by python-dotenv.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

startup_exports="$(uv run python -m level_bridge.env_export)"
eval "${startup_exports}"

exec uv run uvicorn main:app --reload --port "${PORT:-8000}"
