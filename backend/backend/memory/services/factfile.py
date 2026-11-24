"""Fact files: `---` frontmatter (key: value lines) then the body."""

import re
import unicodedata
from dataclasses import dataclass

_KEY = re.compile(r"^([a-z_]+):\s?(.*)$")


@dataclass
class FactFile:
    id: str
    name: str
    description: str
    kind: str
    body: str


def one_line(text: str) -> str:
    """NFKC-normalised single line (look-alike forms must not make duplicates)."""
    return " ".join(unicodedata.normalize("NFKC", text).split())


def render(fact: FactFile) -> str:
    head = (
        f"---\nid: {fact.id}\nname: {one_line(fact.name)}\n"
        f"description: {one_line(fact.description)}\ntype: {fact.kind}\n---\n"
    )
    return head + fact.body.strip() + "\n"


def parse(text: str) -> FactFile | None:
    """None when the file has no frontmatter or no name."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    meta: dict[str, str] = {}
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            body = "\n".join(lines[i + 1 :]).strip()
            break
        m = _KEY.match(line)
        if m:
            meta[m[1]] = m[2].strip()
    else:
        return None
    if not meta.get("name"):
        return None
    return FactFile(
        meta.get("id", ""),
        meta["name"],
        meta.get("description", ""),
        meta.get("type", "project"),
        body,
    )
