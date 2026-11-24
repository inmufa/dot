#!/bin/sh
# Create the protected .dot files before compose bind-mounts them read-only.
# DOT_WORKSPACE_DIR is relative to deploy/compose (as in .env.example).
set -eu
root="$(cd "$(dirname "$0")/../.." && pwd)"
dir="${DOT_WORKSPACE_DIR:-$(sed -n 's/^DOT_WORKSPACE_DIR=//p' "$root/.env" 2>/dev/null | tail -n1)}"
dir="${dir:-../../workspace}"
cd "$root/deploy/compose"
mkdir -p "$dir/.dot/hooks"
[ -f "$dir/.dot/settings.json" ] || echo '{}' > "$dir/.dot/settings.json"
