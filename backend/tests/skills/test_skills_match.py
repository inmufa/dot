import sys
from pathlib import Path

import pytest
from backend.cognition.services.skill_loader import SkillRegistry

BUNDLED = Path(__file__).resolve().parents[3] / "skills"


@pytest.fixture(scope="module")
def registry() -> SkillRegistry:
    reg = SkillRegistry(BUNDLED)
    reg.env.which = lambda b: b  # ranking only: pretend every binary exists
    reg.set_environment({"Read", "Write", "Edit", "Glob", "Grep", "Bash", "Skill"})
    return reg


QUERIES = [
    ("review my pull request for bugs", "code-review"),
    ("write a django REST serializer and viewset", "django-expert"),
    ("optimize this slow postgres query with an index", "postgres-pro"),
    ("create a pptx slide deck", "pptx"),
    ("fix flaky playwright e2e tests", "playwright-expert"),
    ("design a rest api openapi spec with pagination", "api-designer"),
    ("react native navigation with expo", "react-native-expert"),
    ("extract text from a pdf file", "pdf"),
    ("typescript generics and conditional types", "typescript-pro"),
    ("security audit for sql injection and xss", "security-review"),
    ("excel spreadsheet formulas", "xlsx"),
    ("play devil's advocate and challenge my plan", "the-fool"),
    ("reverse engineer this legacy codebase", "spec-miner"),
    ("vue pinia store composition api", "vue-expert"),
    ("create a DOT.md for this repo", "init"),
    ("schedule this to run every night with cron", "schedule"),
]


@pytest.mark.parametrize(("query", "expected"), QUERIES)
def test_bm25_ranking(registry: SkillRegistry, query: str, expected: str):
    names = [s.name for s in registry.index().match(query)]
    assert expected in names[:3], names


@pytest.mark.parametrize("query", ["hello how are you", "thanks", "ok do it"])
def test_chitchat_matches_nothing(registry: SkillRegistry, query: str):
    assert registry.index().match(query) == []


def test_hint_format_and_cap(registry: SkillRegistry):
    hint = registry.hint("review my pull request for bugs and security")
    assert hint.startswith("<system-reminder>\nSkills that may apply:")
    assert hint.endswith("Use the Skill tool to load.\n</system-reminder>")
    assert len([ln for ln in hint.splitlines() if " - " in ln]) <= 3


def test_hint_empty_for_slash_and_chitchat(registry: SkillRegistry):
    assert registry.hint("/code-review the diff") == ""
    assert registry.hint("hello") == ""


def test_unavailable_and_user_only_skills_not_matched(tmp_path: Path):
    for name, extra in (
        ("hidden", "disable-model-invocation: true"),
        ("gone", "requires: {binaries: [zzz-nope]}"),
    ):
        d = tmp_path / name
        d.mkdir()
        (d / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: quantum zebra wrangling\n{extra}\n---\nbody\n"
        )
    assert (
        SkillRegistry(tmp_path).index(fresh=True).match("quantum zebra wrangling") == []
    )


def test_every_bundled_skill_loads(
    registry: SkillRegistry, capsys: pytest.CaptureFixture
):
    idx = registry.index(fresh=True)
    assert idx.issues == []
    avail = [s for s in idx.skills.values() if s.available]
    gone = [s for s in idx.skills.values() if not s.available]
    assert len(idx.skills) >= 45
    for native in (
        "code-review",
        "simplify",
        "security-review",
        "init",
        "loop",
        "schedule",
        "run",
        "update-config",
        "dot-help",
    ):
        assert idx.skills[native].available
        lines = (BUNDLED / native / "SKILL.md").read_text().count("\n")
        assert lines <= 120
    for s in gone:
        assert s.reason
    with capsys.disabled():
        sys.stdout.write(
            f"\nbundled skills: {len(idx.skills)} total, {len(avail)} available, {len(gone)} unavailable"
            "\n"
        )
