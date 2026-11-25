"""AES-256-GCM sealing. Blob = 12-byte random nonce + ciphertext + tag."""

import os
import re

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_NONCE = 12
_HEX_KEY = re.compile(r"^[0-9a-fA-F]{64}$")


class VaultDataError(Exception):
    """A record failed authentication: wrong key, tampering or a moved record."""


def parse_key(raw: str | None) -> bytes | None:
    """32-byte key from 64 hex chars; None when unset. Never echoes the value."""
    if not raw or not raw.strip():
        return None
    if not _HEX_KEY.match(raw.strip()):
        msg = "DOT_VAULT_KEY must be 64 hex characters (32 bytes)"
        raise ValueError(msg)
    return bytes.fromhex(raw.strip())


def aad(record_id: str, kind: str, origins: list[str]) -> bytes:
    """Binds a blob to its record, purpose and origin list."""
    return f"{record_id}|{kind}|{','.join(sorted(origins))}".encode()


def seal(key: bytes, plaintext: bytes, associated: bytes) -> bytes:
    nonce = os.urandom(_NONCE)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, associated)


def unseal(key: bytes, blob: bytes, associated: bytes) -> bytes:
    if len(blob) <= _NONCE:
        msg = "vault record is truncated"
        raise VaultDataError(msg)
    try:
        return AESGCM(key).decrypt(blob[:_NONCE], blob[_NONCE:], associated)
    except InvalidTag as exc:
        msg = "vault record failed authentication"
        raise VaultDataError(msg) from exc
