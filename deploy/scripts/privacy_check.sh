#!/usr/bin/env bash
# Re-runs the privacy invariants against the RUNNING stack (docs/privacy.md). PASS/FAIL per
# check, exit 1 on any FAIL. Read-only: it never prints .env values or changes anything.
set -u
root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"
fails=0
pass() { printf 'PASS  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; fails=$((fails + 1)); }
check() { if eval "$2" >/dev/null 2>&1; then pass "$1"; else fail "$1"; fi; }
cid() { docker ps -q --filter "label=com.docker.compose.project=dot" --filter "label=com.docker.compose.service=$1" | head -n1; }

# TCP to a public IP and a DNS lookup from inside the container. Prints OPEN / DNS when reachable.
PROBE='import socket
s=socket.socket();s.settimeout(3)
try:
    s.connect(("1.1.1.1",443));print("OPEN")
except OSError:
    pass
try:
    socket.gethostbyname("example.com");print("DNS")
except OSError:
    pass'
probe() { # service -> output of the probe
  local c; c="$(cid "$1")"
  case "$1" in
    dot-web) docker exec "$c" node -e '
      const n=require("net"),d=require("dns");
      const s=n.connect({host:"1.1.1.1",port:443,timeout:3000},()=>{console.log("OPEN");s.destroy()});
      s.on("error",()=>{});s.on("timeout",()=>s.destroy());
      d.lookup("example.com",(e)=>{if(!e)console.log("DNS")});setTimeout(()=>process.exit(0),4500)' 2>&1 ;;
    dot-llm) docker exec "$c" sh -c 'curl -s -m3 -o /dev/null https://1.1.1.1 && echo OPEN; getent hosts example.com >/dev/null 2>&1 && echo DNS' 2>&1 ;;
    *) docker exec "$c" python3 -c "$PROBE" 2>&1 ;;
  esac
}

echo "== egress (runtime, from inside each container)"
for svc in dot-llm dot-sandbox dot-voice dot-web; do
  [ -n "$(cid "$svc")" ] || { echo "SKIP  $svc not running"; continue; }
  out="$(probe "$svc")"
  case "$out" in *OPEN*) fail "$svc reaches the internet (TCP 1.1.1.1:443)" ;; *) pass "$svc cannot reach the internet" ;; esac
  case "$out" in *DNS*) fail "$svc resolves public DNS names (leak)" ;; *) pass "$svc cannot resolve public DNS names" ;; esac
done
# By design: backend (WebFetch) and searxng reach out. They must have exactly the documented routes.
for svc in dot-backend dot-searxng; do
  c="$(cid "$svc")"; [ -n "$c" ] || continue
  nets="$(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$c")"
  exp="dot_dot-core dot_dot-fetch dot_dot-publish dot_dot-sandbox-link dot_dot-search-link dot_dot-browser-link dot_dot-voice-link"
  [ "$svc" = dot-searxng ] && exp="dot_dot-search dot_dot-search-link"
  extra=""
  for n in $nets; do case " $exp " in *" $n "*) ;; *) extra="$extra $n" ;; esac; done
  [ -z "$extra" ] && pass "$svc is only on its documented networks" || fail "$svc is on unexpected networks:$extra"
done

echo "== isolation between containers"
c="$(cid dot-sandbox)"
if [ -n "$c" ]; then
  out="$(docker exec "$c" python3 -c '
import socket
for h in ("dot-llm","dot-searxng","dot-web","dot-browser","dot-voice"):
    try:
        socket.gethostbyname(h);print("RESOLVES",h)
    except OSError:
        pass
for ip in ("172.17.0.1","192.168.1.1","169.254.169.254"):
    s=socket.socket();s.settimeout(2)
    try:
        s.connect((ip,80));print("OPEN",ip)
    except OSError:
        pass' 2>&1)"
  [ -z "$out" ] && pass "sandbox sees only the backend (no llm, searxng, web, LAN, metadata)" || fail "sandbox reaches: $(echo "$out" | tr '\n' ' ')"
fi
for n in dot_dot-core dot_dot-sandbox-link dot_dot-search-link dot_dot-browser-link dot_dot-voice-link; do
  v="$(docker network inspect "$n" -f '{{.Internal}}' 2>/dev/null)"
  [ "$v" = true ] && pass "network $n is internal" || fail "network $n is not internal ($v)"
done
v="$(docker network inspect dot_dot-publish -f '{{index .Options "com.docker.network.bridge.enable_ip_masquerade"}}' 2>/dev/null)"
[ "$v" = false ] && pass "network dot_dot-publish has no NAT" || fail "network dot_dot-publish masquerades ($v)"

echo "== exposed ports"
bad="$(docker ps --filter "label=com.docker.compose.project=dot" --format '{{.Names}} {{.Ports}}' | grep -oE '[^ ,]*->[0-9]+/tcp' | grep -vE '^(127\.0\.0\.1|\[::1\]):' || true)"
[ -z "$bad" ] && pass "every published port binds loopback" || fail "published beyond loopback: $bad"

echo "== container hardening"
for c in $(docker ps -q --filter "label=com.docker.compose.project=dot"); do
  n="$(docker inspect -f '{{.Name}}' "$c" | tr -d /)"
  info="$(docker inspect -f '{{.HostConfig.Privileged}}|{{.HostConfig.NetworkMode}}|{{.HostConfig.CapDrop}}|{{range .Mounts}}{{.Source}} {{end}}' "$c")"
  case "$info" in true*) fail "$n is privileged"; continue ;; esac
  case "$info" in *"|host|"*) fail "$n uses host networking"; continue ;; esac
  case "$info" in *docker.sock*) fail "$n mounts the docker socket"; continue ;; esac
  case "$info" in *ALL*) pass "$n: not privileged, caps dropped, no socket" ;; *) fail "$n does not drop all capabilities" ;; esac
done

echo "== secrets and files"
mode="$(stat -c %a .env 2>/dev/null || echo missing)"
[ "$mode" = 600 ] && pass ".env is mode 600" || fail ".env mode is $mode (want 600)"
check ".env is git-ignored" "git check-ignore -q .env"
check "no .env file is tracked" "[ -z \"\$(git ls-files | grep -E '(^|/)\\.env\$')\" ]"
owner="$(sed -n 's/^DOT_OWNER_EMAIL=//p' .env 2>/dev/null | tail -n1)"
if [ -z "$owner" ]; then pass "owner email check skipped (set DOT_OWNER_EMAIL in .env to enable)"
elif grep -rIlF "$owner" --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=.git --exclude-dir='.next*' . 2>/dev/null | grep -q .; then fail "owner email found in the tree"; else pass "owner email is not in the tree"; fi
c="$(cid dot-backend)"
if [ -n "$c" ]; then
  m="$(docker exec "$c" sh -c 'stat -c %a /data /data/dot.db' 2>/dev/null | tr '\n' ' ')"
  [ "$m" = "700 600 " ] && pass "backend data dir 700, database 600" || fail "backend data perms are: $m"
  code="$(curl -s -m5 -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/openapi.json)"
  [ "$code" = 404 ] && pass "OpenAPI and /docs are off" || fail "/openapi.json answers $code"
  env="$(docker exec "$c" env)"
  case "$env" in *DO_NOT_TRACK=1*) pass "backend DO_NOT_TRACK=1" ;; *) fail "backend DO_NOT_TRACK not set" ;; esac
  case "$env" in *DOT_LLM_DEBUG_FILE=$'\n'*|*DOT_LLM_DEBUG_FILE=) pass "LLM debug capture is off" ;; *) fail "DOT_LLM_DEBUG_FILE is set" ;; esac
fi
c="$(cid dot-web)"
if [ -n "$c" ]; then
  docker exec "$c" env | grep -q '^NEXT_TELEMETRY_DISABLED=1$' && pass "Next.js telemetry disabled" || fail "NEXT_TELEMETRY_DISABLED not set"
  docker exec "$c" sh -c 'env | grep -E "^DOT_API_TOKEN="' >/dev/null && \
    { if docker exec "$c" sh -c 'grep -rl "$DOT_API_TOKEN" /app/.next/static /app/public 2>/dev/null' | grep -q .; then fail "API token appears in the browser bundle"; else pass "API token is not in the browser bundle"; fi; }
  hosts="$(docker exec "$c" sh -c "grep -rhoE 'https?://[A-Za-z0-9._-]+' /app/.next/static 2>/dev/null | sort -u")"
  ext="$(echo "$hosts" | grep -vE '^https?://(nextjs\.org|www\.w3\.org|github\.com|react\.dev|cdn\.ampproject\.org|127\.0\.0\.1|localhost|[a-z])$' || true)"
  [ -z "$ext" ] && pass "web bundle references only framework doc strings (no CDN, font, analytics host)" || fail "unexpected hosts in web bundle: $(echo "$ext" | tr '\n' ' ')"
fi

echo "== CSP on http://127.0.0.1:3000"
h="$(curl -sI -m5 http://127.0.0.1:3000/ | tr -d '\r')"
csp="$(echo "$h" | grep -i '^content-security-policy:' || true)"
for want in "default-src 'self'" "connect-src 'self'" "img-src 'self' data: blob:" "frame-src 'self'" "form-action 'self'" "base-uri 'none'" "object-src 'none'" "frame-ancestors 'none'"; do
  case "$csp" in *"$want"*) pass "CSP has $want" ;; *) fail "CSP lacks $want" ;; esac
done
case "$csp" in *unsafe-eval*) fail "CSP allows unsafe-eval" ;; *) pass "CSP has no unsafe-eval" ;; esac
echo "$h" | grep -qi '^referrer-policy: no-referrer' && pass "Referrer-Policy no-referrer" || fail "Referrer-Policy missing"

echo
if [ "$fails" -eq 0 ]; then echo "privacy-check: all checks passed"; else echo "privacy-check: $fails FAILED"; fi
[ "$fails" -eq 0 ]
