"""RFC 6238 TOTP (SHA1, 30 s, 6 digits). The code is computed only inside a login call."""

import base64
import hashlib
import hmac
import struct
import time


def totp_code(secret: str, now: float | None = None) -> str:
    cleaned = "".join(secret.split()).upper().rstrip("=")
    key = base64.b32decode(cleaned + "=" * (-len(cleaned) % 8))
    counter = int((time.time() if now is None else now) // 30)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{value % 1_000_000:06d}"
