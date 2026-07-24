#!/usr/bin/env bash
# Starts the Econ Calendar API with uvicorn.
# Configure via environment variables or a .env file (see .env.example).
set -euo pipefail

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
WORKERS="${WORKERS:-1}"

exec uvicorn app.main:app --host "$HOST" --port "$PORT" --workers "$WORKERS"
