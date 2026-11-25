#!/bin/sh
# Optional host firewall for Dot's Docker networks (docs/privacy.md). Docker alone cannot stop a
# container from reaching the LAN, cloud metadata or host services on the bridge gateway.
#   egress nets (browsing, fetch, search): private/special ranges dropped (DOCKER-USER) and the
#       host itself closed to them (INPUT).
#   publish net: no new connection may start from it at all (it only carries published ports).
# Prints the iptables rules by default; nothing changes unless you pass --apply (root; rules live
# in DOCKER-USER/INPUT and are lost on reboot). Undo with --remove.
set -eu
mode="${1:-print}"
project="${DOT_COMPOSE_PROJECT:-dot_dot}"
egress="${DOT_EGRESS_NETWORKS:-$project-browsing $project-fetch $project-search}"
publish="${DOT_PUBLISH_NETWORK:-$project-publish}"
blocked="0.0.0.0/8 10.0.0.0/8 100.64.0.0/10 127.0.0.0/8 169.254.0.0/16 172.16.0.0/12 192.168.0.0/16 224.0.0.0/4"

emit() { # chain, then the rule spec
  chain="$1"; shift
  case "$mode" in
    --apply) iptables -C "$chain" "$@" 2>/dev/null || iptables -I "$chain" "$@" ;;
    --remove) iptables -D "$chain" "$@" 2>/dev/null || true ;;
    *) echo "iptables -I $chain $*" ;;
  esac
}
subnet() { docker network inspect "$1" -f '{{(index .IPAM.Config 0).Subnet}}' 2>/dev/null || true; }

for net in $egress; do
  s="$(subnet "$net")"
  [ -n "$s" ] || { echo "# skip $net (not created)" >&2; continue; }
  for dst in $blocked; do emit DOCKER-USER -s "$s" -d "$dst" -j DROP; done
  emit INPUT -s "$s" -m conntrack --ctstate NEW -j DROP
done
s="$(subnet "$publish")"
if [ -n "$s" ]; then
  emit DOCKER-USER -s "$s" '!' -d "$s" -m conntrack --ctstate NEW -j DROP
  emit INPUT -s "$s" -m conntrack --ctstate NEW -j DROP
fi
