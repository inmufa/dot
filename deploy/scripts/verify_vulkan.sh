#!/usr/bin/env bash
# Host diagnostic for the llama.cpp Vulkan backend (RX 580 / RADV). Read-only.
# Prints what it finds and the docker command that proves GPU access from a container.
set -u

pass() { printf '[ ok ] %s\n' "$*"; }
warn() { printf '[warn] %s\n' "$*"; }
fail() { printf '[FAIL] %s\n' "$*"; }
status=0

echo "== /dev/dri =="
if ls -l /dev/dri 2>/dev/null; then
  ls /dev/dri/renderD* >/dev/null 2>&1 && pass "render node present" \
    || { fail "no /dev/dri/renderD* node"; status=1; }
else
  fail "/dev/dri missing (no GPU driver loaded?)"; status=1
fi

echo
echo "== group membership (user: $(id -un)) =="
for g in video render docker; do
  if id -nG | tr ' ' '\n' | grep -qx "$g"; then pass "in group $g (gid $(getent group "$g" | cut -d: -f3))"
  else warn "not in group $g (log out/in after: sudo usermod -aG $g $USER)"; fi
done
echo "Compose needs numeric gids in .env:"
echo "  DOT_VIDEO_GID=$(getent group video | cut -d: -f3)"
echo "  DOT_RENDER_GID=$(getent group render | cut -d: -f3)"

echo
echo "== vulkaninfo --summary =="
if command -v vulkaninfo >/dev/null 2>&1; then
  out="$(vulkaninfo --summary 2>&1)"
  printf '%s\n' "$out" | sed -n '1,40p'
  if printf '%s' "$out" | grep -Eqi 'radv|polaris|RX 580'; then pass "RADV / Polaris device listed"
  else fail "no RADV device (install mesa-vulkan-drivers; check the kernel amdgpu module)"; status=1; fi
  printf '%s' "$out" | grep -qi llvmpipe && warn "llvmpipe (CPU) is also listed: llama.cpp must pick the RADV device"
else
  fail "vulkaninfo not found (apt install vulkan-tools mesa-vulkan-drivers)"; status=1
fi

echo
echo "== kernel driver =="
lsmod 2>/dev/null | grep -E '^amdgpu' || warn "amdgpu module not listed"

echo
echo "== docker GPU test (run it yourself) =="
cat <<CMD
docker run --rm --device /dev/dri --group-add "\$(getent group video | cut -d: -f3)" \\
  --group-add "\$(getent group render | cut -d: -f3)" \\
  --entrypoint sh ghcr.io/ggml-org/llama.cpp:server-vulkan-b12464 \\
  -c 'ls -l /dev/dri; llama-server --list-devices 2>&1 | head -20'
CMD
echo "Expected: a line naming Vulkan0 with the Radeon RX 580. Only CPU listed means the device or groups did not reach the container."
exit "$status"
