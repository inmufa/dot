"""Skill registry: scan tiers, resolve precedence, match, expand."""

import time
from collections.abc import Awaitable, Callable
from pathlib import Path

from backend.cognition.services.skills import frontmatter
from backend.cognition.services.skills.bm25 import Bm25, tokenize
from backend.cognition.services.skills.model import Skill, SkillIssue
from backend.cognition.services.skills.requires import (
    Environment,
    unavailable_reason,
)
from backend.core.exceptions import DomainException
from backend.routing.clients.sandbox_client import SandboxClient

CACHE_TTL_S = 5.0
BINARIES_TTL_S = 60.0
BinaryProbe = Callable[[list[str]], Awaitable[set[str] | None]]
MATCH_THRESHOLD = 4.0
RELATIVE_CUTOFF = 0.3  # drop hits far below the best one
MAX_MATCHES = 3
QUERY_CAP = 2000
_NAME_WEIGHT = 3


def _plain(text: str) -> str:
    """Descriptions come from files: no tags may reach the reminder block."""
    return text.replace("<", "").replace(">", "")


def scan_dir(root: Path, source: str) -> tuple[list[Skill], list[SkillIssue]]:
    skills: list[Skill] = []
    issues: list[SkillIssue] = []
    if not root.is_dir():
        return skills, issues
    for child in sorted(root.iterdir()):
        if not (child / "SKILL.md").is_file():
            continue
        skill, issue = frontmatter.read_skill(child, source)  # type: ignore[arg-type]
        if skill:
            skills.append(skill)
        if issue:
            issues.append(issue)
    return skills, issues


class SkillIndex:
    def __init__(self, skills: dict[str, Skill], issues: list[SkillIssue]) -> None:
        self.skills = skills
        self.issues = issues
        docs = {
            s.name: tokenize(
                f"{' '.join([s.name.replace('-', ' ')] * _NAME_WEIGHT)} "
                f"{s.description} {' '.join(s.triggers)}"
            )
            for s in skills.values()
            if s.available and s.model_invocable
        }
        self._bm25 = Bm25(docs)

    def match(self, text: str) -> list[Skill]:
        query = tokenize(text[:QUERY_CAP])
        ranked = sorted(self._bm25.scores(query).items(), key=lambda kv: -kv[1])
        return [self.skills[n] for n, s in ranked[:MAX_MATCHES] if s >= MATCH_THRESHOLD]


class SkillRegistry:
    """Tiers: workspace `.dot/skills` > user dir > bundled dir."""

    def __init__(
        self, bundled: Path, user: Path | None = None, workspace: Path | None = None
    ) -> None:
        self._bundled = bundled
        self._user = user
        self._workspace = workspace
        self.env = Environment()
        self._cache: tuple[float, SkillIndex] | None = None
        self.probe: BinaryProbe | None = None  # asks the sandbox which binaries exist
        self._probed_at = float("-inf")

    async def ensure_binaries(self) -> None:
        """Refresh which required binaries exist in the sandbox (cached for a minute)."""
        now = time.monotonic()
        if self.probe is None or now - self._probed_at < BINARIES_TTL_S:
            return
        names = sorted(
            {
                b
                for s in self.index(fresh=True).skills.values()
                for b in s.requires.binaries
            }
        )
        found = await self.probe(names) if names else set()
        if found is None and self.env.binaries is not None:
            return  # keep the last good answer
        self._probed_at = now if found is not None else float("-inf")
        self.env.binaries = found
        self._cache = None

    def set_environment(self, tools: set[str], mcp: set[str] | None = None) -> None:
        self.env.tools = set(tools)
        self.env.mcp = set(mcp or ())
        self._cache = None

    def index(self, *, fresh: bool = False) -> SkillIndex:
        now = time.monotonic()
        if not fresh and self._cache and now - self._cache[0] < CACHE_TTL_S:
            return self._cache[1]
        built = self._build()
        self._cache = (now, built)
        return built

    def _build(self) -> SkillIndex:
        tiers = [
            (
                self._workspace / ".dot" / "skills" if self._workspace else None,
                "workspace",
            ),
            (self._user, "user"),
            (self._bundled, "bundled"),
        ]
        merged: dict[str, Skill] = {}
        issues: list[SkillIssue] = []
        for root, source in tiers:
            if root is None:
                continue
            found, bad = scan_dir(root, source)
            issues.extend(bad)
            for skill in found:
                if skill.name in merged:
                    msg = f"shadowed by {merged[skill.name].source} skill"
                    issues.append(SkillIssue(str(skill.path), msg))
                    continue
                skill.reason = unavailable_reason(skill.requires, self.env)
                skill.available = skill.reason is None
                merged[skill.name] = skill
        return SkillIndex(merged, issues)

    def get(self, name: str) -> Skill | None:
        return self.index().skills.get(name)

    def hint(self, text: str) -> str:
        """Per-turn reminder block naming up to 3 matching skills ('' if none)."""
        if text.lstrip().startswith("/"):
            return ""
        hits = self.index().match(text)
        if not hits:
            return ""
        lines = "\n".join(f"{s.name} - {_plain(s.description)}" for s in hits)
        return (
            "<system-reminder>\n"
            f"Skills that may apply:\n{lines}\n"
            "Use the Skill tool to load.\n"
            "</system-reminder>"
        )


def sandbox_probe(sandbox: SandboxClient) -> BinaryProbe:
    async def probe(names: list[str]) -> set[str] | None:
        try:
            r = await sandbox.post("skills", "/internal/binaries", {"names": names})
        except DomainException:
            return None
        found = r.data.get("found")
        return set(found) if r.ok and isinstance(found, list) else None

    return probe
