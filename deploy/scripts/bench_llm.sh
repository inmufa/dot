#!/usr/bin/env bash
# M0 gate: llama-bench through the dot-llm image (Vulkan in docker). Prints a markdown
# table. Run it once natively too and compare (instructions at the bottom of this output).
#
#   deploy/scripts/bench_llm.sh [model-file-in-./models]   (default: DOT_MODEL_FILE)
#
# Env: DOT_BENCH_IMAGE (default: the image pinned in compose), DOT_BENCH_PP (512),
#      DOT_BENCH_TG (128), DOT_BENCH_REPS (3), DOT_BENCH_NGL (99).
# Docker only: the native comparison is printed, not run.
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
model="${1:-$(sed -n 's/^DOT_MODEL_FILE=//p' "$root/.env" 2>/dev/null | tail -n1)}"
model="${model:-model.gguf}"
tag="$(sed -n 's/^DOT_LLM_IMAGE_TAG=//p' "$root/.env" 2>/dev/null | tail -n1)"
tag="${tag:-$(sed -n 's#.*image: ghcr.io/ggml-org/llama.cpp:${DOT_LLM_IMAGE_TAG:-\([^}]*\)}.*#\1#p' "$root/deploy/compose/compose.base.yml" | head -n1)}"
image="${DOT_BENCH_IMAGE:-ghcr.io/ggml-org/llama.cpp:$tag}"
pp="${DOT_BENCH_PP:-512}"; tg="${DOT_BENCH_TG:-128}"; reps="${DOT_BENCH_REPS:-3}"; ngl="${DOT_BENCH_NGL:-99}"
video="$(getent group video | cut -d: -f3)"; render="$(getent group render | cut -d: -f3)"

[ -f "$root/models/$model" ] || { echo "models/$model not found (make models)" >&2; exit 1; }
command -v docker >/dev/null || { echo "docker not installed" >&2; exit 1; }

echo "## llama-bench in docker ($image)"
echo
docker run --rm --device /dev/dri --group-add "$video" --group-add "$render" \
  -v "$root/models:/models:ro" --entrypoint llama-bench "$image" \
  -m "/models/$model" -ngl "$ngl" -fa 1 -ctk q8_0 -ctv q8_0 \
  -p "$pp" -n "$tg" -r "$reps" -o md

cat <<EOF2

## Gate procedure
1. M0 (native vs docker): build or download a native llama.cpp Vulkan build (same release as
   the image tag above) and run
     llama-bench -m models/$model -ngl $ngl -fa 1 -ctk q8_0 -ctv q8_0 -p $pp -n $tg -r $reps -o md
   Compare the 'pp$pp' and 'tg$tg' t/s columns with the table above. Docker within ~5% of
   native passes. A larger gap: re-run scripts/verify_vulkan.sh and check device/group access.
2. M1 (model gate): start the stack (make up), then
     make gate        # deploy/scripts/m1_model_gate.py: 20 tool-call tasks + prefix-reuse probe
   Pass: tool-call success >= 90% and later-turn prompt-eval time well below turn 1 (cache reused).
3. Record both tables with the model file name and quantisation next to DOT_MODEL_FILE.
EOF2
