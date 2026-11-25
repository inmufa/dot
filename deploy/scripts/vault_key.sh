#!/bin/sh
# Create DOT_VAULT_KEY in .env if absent. Never prints the key.
set -eu
cd "$(dirname "$0")/../.."
umask 077
touch .env
chmod 600 .env
if grep -Eq '^DOT_VAULT_KEY=.+' .env; then
  echo "DOT_VAULT_KEY already set in .env (left unchanged)"
  exit 0
fi
key=$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')
sed -i '/^DOT_VAULT_KEY=/d' .env
printf 'DOT_VAULT_KEY=%s\n' "$key" >> .env
chmod 600 .env
echo "DOT_VAULT_KEY written to .env (mode 600). Back it up: without it saved logins cannot be decrypted."
