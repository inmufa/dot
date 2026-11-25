#!/usr/bin/env bash
# docker compose with the overlay for DOT_GPU_BACKEND (.env): deploy/scripts/compose.sh <args>
# DOT_COMPOSE_DRY=1 prints the command instead of running it.
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"
backend="$(sed -n 's/^DOT_GPU_BACKEND=//p' .env 2>/dev/null | tail -n1)"
backend="${backend:-vulkan}"
case "$backend" in
  vulkan | cuda | rocm | cpu) ;;
  *) echo "DOT_GPU_BACKEND must be vulkan, cuda, rocm or cpu (got: $backend)" >&2; exit 2 ;;
esac

files=(-f deploy/compose/compose.base.yml)
[ "$backend" = cpu ] || files+=(-f "deploy/compose/compose.gpu-$backend.yml")
[ -f deploy/compose/compose.local.yml ] && files+=(-f deploy/compose/compose.local.yml)

# DOT_VOICE=on (hardware profile) starts the voice worker; it needs a token.
voice="$(sed -n 's/^DOT_VOICE=//p' .env 2>/dev/null | tail -n1)"
profiles=()
if [ "$voice" = on ]; then
  if grep -Eq '^DOT_VOICE_TOKEN=.+' .env; then
    profiles+=(--profile voice)
  else
    echo "DOT_VOICE=on but DOT_VOICE_TOKEN is empty in .env: voice stays off" >&2
  fi
fi

cmd=(docker compose --env-file .env "${files[@]}" "${profiles[@]}" "$@")
if [ -n "${DOT_COMPOSE_DRY:-}" ]; then
  printf '%s\n' "${cmd[*]}"
else
  exec "${cmd[@]}"
fi
