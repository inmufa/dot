#!/bin/sh
# Kept for old docs: the browser rules are part of firewall_dot.sh now.
exec sh "$(dirname "$0")/firewall_dot.sh" "$@"
