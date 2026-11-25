#!/usr/bin/env bash
# Switch the served model: deploy/scripts/switch_model.sh <file.gguf | stem | registry name>
# Updates .env (model, projector, context via the applied profile) and recreates dot-llm.
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
name="${1:-}"
case "$name" in
  "" | */* | ..* | *[!A-Za-z0-9._+-]*) echo "usage: make model NAME=<file or stem from ./models>" >&2; exit 2 ;;
  mmproj*) echo "mmproj files are projectors, not models" >&2; exit 2 ;;
esac

cd "$root"
uv run python deploy/scripts/dotctl.py model "$name"
bash deploy/scripts/compose.sh up -d --force-recreate dot-llm
# The backend only restarts when its env (context seed, slots) changed.
exec bash deploy/scripts/compose.sh up -d dot-backend
