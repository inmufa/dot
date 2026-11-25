"""Rotate DOT_VAULT_KEY: re-encrypt every vault blob under a fresh key.

Run with the backend stopped: `make vault-rotate`. The old database is copied first.
Keys are never printed.
"""

import argparse
import json
import os
import secrets
import shutil
import sqlite3
import time
from pathlib import Path

from backend.vault import crypto

_BLOBS = (("secret", "secret_blob"), ("session", "session_blob"))
_KEY_LINE = "DOT_VAULT_KEY="


def _env_key(env: Path) -> str | None:
    for line in env.read_text().splitlines():
        if line.startswith(_KEY_LINE):
            return line.removeprefix(_KEY_LINE).strip().strip("'\"") or None
    return None


def _write_env(env: Path, new_key: str) -> Path:
    lines = [ln for ln in env.read_text().splitlines() if not ln.startswith(_KEY_LINE)]
    tmp = env.with_name(env.name + ".rotate-new")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write("\n".join([*lines, f"{_KEY_LINE}{new_key}"]) + "\n")
    return tmp


def reseal(db_path: Path, old: bytes, new: bytes) -> int:
    """Re-encrypt all rows in one transaction; any failure rolls everything back."""
    con = sqlite3.connect(db_path, timeout=10)
    try:
        con.execute("BEGIN IMMEDIATE")
        rows = con.execute(
            "SELECT id, public_id, origins, secret_blob, session_blob FROM vault_credentials"
        ).fetchall()
        for rid, pid, origins_json, *blobs in rows:
            origins = json.loads(origins_json)
            for (kind, col), blob in zip(_BLOBS, blobs, strict=True):
                if blob is None:
                    continue
                aad = crypto.aad(pid, kind, origins)
                fresh = crypto.seal(new, crypto.unseal(old, blob, aad), aad)
                con.execute(
                    f"UPDATE vault_credentials SET {col}=? WHERE id=?",  # noqa: S608
                    (fresh, rid),
                )
        con.commit()
        return len(rows)
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()


def _backup(db_path: Path) -> None:
    dest = db_path.with_name(f"{db_path.name}.pre-rotate-{int(time.time())}")
    shutil.copy2(db_path, dest)
    dest.chmod(0o600)


def rotate_from_env(db_path: Path, *, backup: bool = True) -> int:
    """Container mode: old key in DOT_VAULT_KEY, new key in DOT_VAULT_NEW_KEY."""
    old = crypto.parse_key(os.environ.get("DOT_VAULT_KEY"))
    new = crypto.parse_key(os.environ.get("DOT_VAULT_NEW_KEY"))
    if old is None or new is None:
        msg = "DOT_VAULT_KEY and DOT_VAULT_NEW_KEY must both be set"
        raise SystemExit(msg)
    if backup:
        _backup(db_path)
    return reseal(db_path, old, new)


def rotate(env: Path, db_path: Path, *, backup: bool = True) -> int:
    old = crypto.parse_key(_env_key(env))
    if old is None:
        msg = "no DOT_VAULT_KEY in the env file: nothing to rotate"
        raise SystemExit(msg)
    if backup:
        _backup(db_path)
    new_hex = secrets.token_hex(32)
    staged = _write_env(env, new_hex)
    try:
        count = reseal(db_path, old, bytes.fromhex(new_hex))
    except BaseException:
        staged.unlink(missing_ok=True)
        raise
    staged.replace(env)
    return count


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--env", type=Path, default=Path(".env"))
    ap.add_argument("--db", type=Path, default=Path("data/dot.db"))
    ap.add_argument("--no-backup", action="store_true")
    ap.add_argument(
        "--from-env", action="store_true", help="keys come from the environment"
    )
    args = ap.parse_args()
    if args.from_env:
        count = rotate_from_env(args.db, backup=not args.no_backup)
    else:
        count = rotate(args.env, args.db, backup=not args.no_backup)
    print(f"rotated {count} vault record(s); restart the backend")  # noqa: T201


if __name__ == "__main__":
    main()
