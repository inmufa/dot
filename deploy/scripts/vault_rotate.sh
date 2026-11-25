#!/bin/sh
# Rotate DOT_VAULT_KEY: stop the backend, re-encrypt the vault inside a one-off container
# (the database lives in the dot-data volume), then store the new key in .env and restart.
# Keys are passed by environment name only and never printed.
set -eu
cd "$(dirname "$0")/../.."
grep -Eq '^DOT_VAULT_KEY=.+' .env || { echo "no DOT_VAULT_KEY in .env: run make vault-key"; exit 1; }
COMPOSE="bash deploy/scripts/compose.sh"
new=$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')
$COMPOSE stop dot-backend
DOT_VAULT_NEW_KEY=$new
export DOT_VAULT_NEW_KEY
$COMPOSE run --rm --no-deps -e DOT_VAULT_NEW_KEY dot-backend \
  python -m backend.vault.rotate --from-env --db /data/dot.db
umask 077
sed -i '/^DOT_VAULT_KEY=/d' .env
printf 'DOT_VAULT_KEY=%s\n' "$new" >> .env
chmod 600 .env
$COMPOSE up -d --no-deps dot-backend
echo "vault key rotated; .env updated. The old key is useless now, but a pre-rotate DB copy in the dot-data volume still needs it."
