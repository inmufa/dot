#!/bin/sh
# Optional host firewall for the dot-browser egress network (dot-browsing).
# Docker alone cannot stop a container from reaching the LAN or cloud metadata.
# Prints the iptables rules by default; nothing is changed unless you pass --apply
# (needs root, rules live in DOCKER-USER and are lost on reboot). Remove with --remove.
set -eu
mode="${1:-print}"
net="${DOT_BROWSING_NETWORK:-dot_dot-browsing}"
subnet="$(docker network inspect "$net" -f '{{(index .IPAM.Config 0).Subnet}}')"
blocked="10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 100.64.0.0/10 169.254.0.0/16 127.0.0.0/8"
for dst in $blocked; do
  rule="DOCKER-USER -s $subnet -d $dst -j DROP"
  case "$mode" in
    --apply) iptables -C $rule 2>/dev/null || iptables -I $rule ;;
    --remove) iptables -D $rule 2>/dev/null || true ;;
    *) echo "iptables -I $rule" ;;
  esac
done
