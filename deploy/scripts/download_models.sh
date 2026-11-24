#!/usr/bin/env bash
# Fetch a GGUF into ./models with an optional (strongly advised) SHA256 check.
#
#   deploy/scripts/download_models.sh [--repo OWNER/REPO] [--file NAME.gguf]
#                                     [--url URL] [--sha256 HEX]
#
# Settings come from flags, then the environment, then .env (only the DOT_MODEL_* keys
# are read). The file name defaults to DOT_MODEL_FILE. Source:
#   --url / DOT_MODEL_URL           direct download with curl (resumable)
#   --repo + --file / DOT_MODEL_REPO huggingface-cli download, else curl on the resolve URL
# When a SHA256 is given the file is verified and removed on mismatch. Without one the
# script prints the computed hash so you can record it as DOT_MODEL_SHA256.
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"

env_key() {
  [ -f "$root/.env" ] || return 0
  sed -n "s/^$1=//p" "$root/.env" | tail -n1 | tr -d '"'"'"
}

repo="${DOT_MODEL_REPO:-$(env_key DOT_MODEL_REPO)}"
file="${DOT_MODEL_FILE:-$(env_key DOT_MODEL_FILE)}"
url="${DOT_MODEL_URL:-$(env_key DOT_MODEL_URL)}"
sha="${DOT_MODEL_SHA256:-$(env_key DOT_MODEL_SHA256)}"

while [ $# -gt 0 ]; do
  case "$1" in
    --repo) repo="${2:?--repo needs a value}"; shift 2 ;;
    --file) file="${2:?--file needs a value}"; shift 2 ;;
    --url) url="${2:?--url needs a value}"; shift 2 ;;
    --sha256) sha="${2:?--sha256 needs a value}"; shift 2 ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

file="${file:-model.gguf}"
case "$file" in */*|..*) echo "DOT_MODEL_FILE must be a plain file name: $file" >&2; exit 2 ;; esac
if [ -z "$url" ] && [ -z "$repo" ]; then
  echo "set DOT_MODEL_URL, or DOT_MODEL_REPO (OWNER/REPO) with DOT_MODEL_FILE, or pass --url/--repo" >&2
  exit 2
fi
if [ -n "$sha" ] && ! printf '%s' "$sha" | grep -Eq '^[0-9a-fA-F]{64}$'; then
  echo "SHA256 must be 64 hex characters" >&2
  exit 2
fi

dest="$root/models"
mkdir -p "$dest"
target="$dest/$file"

verify() {
  actual="$(sha256sum "$target" | cut -d' ' -f1)"
  if [ -n "$sha" ]; then
    if [ "$actual" != "$(printf '%s' "$sha" | tr 'A-F' 'a-f')" ]; then
      echo "SHA256 mismatch for $file: expected $sha, got $actual" >&2
      rm -f "$target"
      exit 1
    fi
    echo "SHA256 ok: $actual"
  else
    echo "No SHA256 given. Computed: $actual"
    echo "Record it: DOT_MODEL_SHA256=$actual"
  fi
}

# An existing file that already verifies is kept.
if [ -f "$target" ] && [ -n "$sha" ] \
  && [ "$(sha256sum "$target" | cut -d' ' -f1)" = "$(printf '%s' "$sha" | tr 'A-F' 'a-f')" ]; then
  echo "$file already present and verified"
  exit 0
fi

if [ -n "$url" ]; then
  case "$url" in https://*) ;; *) echo "only https URLs are accepted" >&2; exit 2 ;; esac
  curl -fL --retry 3 -C - -o "$target" "$url"
elif command -v huggingface-cli >/dev/null 2>&1; then
  huggingface-cli download "$repo" "$file" --local-dir "$dest"
else
  curl -fL --retry 3 -C - -o "$target" "https://huggingface.co/$repo/resolve/main/$file"
fi

verify
echo "Done: $target (set DOT_MODEL_FILE=$file in .env)"
