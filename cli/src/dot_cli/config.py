"""CLI configuration from arguments and environment."""

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from dot_contracts.permissions import PermissionMode

DEFAULT_URL = "http://127.0.0.1:8000"


@dataclass(frozen=True)
class Config:
    url: str = DEFAULT_URL
    token: str | None = None
    session: str | None = None
    mode: str | None = None
    once: str | None = None


def parse_config(argv: Sequence[str], env: Mapping[str, str]) -> Config:
    parser = argparse.ArgumentParser(prog="dot", description="Dot terminal client")
    parser.add_argument("--url", default=env.get("DOT_URL", DEFAULT_URL))
    parser.add_argument("--token", default=env.get("DOT_API_TOKEN"))
    parser.add_argument("--session", default=env.get("DOT_SESSION"), help="resume id")
    parser.add_argument("--mode", choices=[m.value for m in PermissionMode])
    parser.add_argument("--once", metavar="MESSAGE", help="headless: print answer")
    args = parser.parse_args(argv)
    return Config(args.url, args.token, args.session, args.mode, args.once)
