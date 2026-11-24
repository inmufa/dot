from pathlib import Path

import pytest
from backend.cognition.services.skill_loader import SkillRegistry
from backend.cognition.services.skills import files, frontmatter
from backend.cognition.services.skills.requires import (
    Environment,
    unavailable_reason,
)


def make(root: Path, name: str, fm: str, body: str = "Do the thing.\n") -> Path:
    d = root / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\n{fm}\n---\n{body}")
    return d


def test_parse_full_frontmatter(tmp_path: Path):
    d = make(
        tmp_path,
        "demo",
        "name: demo\ndescription: Does demo things\nlicense: MIT\n"
        "allowed-tools: Read, Grep\ndisable-model-invocation: true\n"
        "metadata:\n  triggers: alpha, beta\n"
        "requires:\n  tools:\n    - Foo\n  binaries: [zzz-nope]\n  mcp: srv\n",
    )
    skill, issue = frontmatter.read_skill(d, "bundled")
    assert issue is None
    assert skill.name == "demo"
    assert skill.license == "MIT"
    assert skill.allowed_tools == ["Read", "Grep"]
    assert skill.triggers == ["alpha", "beta"]
    assert skill.model_invocable is False
    assert skill.requires.tools == ("Foo",)
    assert skill.requires.mcp == ("srv",)
    assert skill.requires.binaries == ("zzz-nope",)


def test_multiline_description_is_flattened_and_capped(tmp_path: Path):
    long = "word " * 200
    d = make(tmp_path, "m", "name: m\ndescription: >\n  first line\n  second line\n")
    skill, _ = frontmatter.read_skill(d, "user")
    assert skill.description == "first line second line"
    d2 = make(tmp_path, "m2", f"name: m2\ndescription: {long}")
    skill2, _ = frontmatter.read_skill(d2, "user")
    assert len(skill2.description) <= 300
    assert skill2.description.endswith("...")


def test_name_falls_back_to_directory(tmp_path: Path):
    d = make(tmp_path, "dirname", "description: no name here")
    skill, issue = frontmatter.read_skill(d, "user")
    assert issue is None
    assert skill.name == "dirname"


@pytest.mark.parametrize(
    ("fm", "needle"),
    [
        ("name: x", "missing description"),
        ("name: x\ndescription: ''", "missing description"),
        ("name: Bad Name\ndescription: d", "invalid skill name"),
        ("name: [unclosed\ndescription: d", "invalid YAML"),
        ("- just\n- a list", "mapping"),
    ],
)
def test_bad_skills_are_reported_not_raised(tmp_path: Path, fm: str, needle: str):
    d = make(tmp_path, "x", fm)
    skill, issue = frontmatter.read_skill(d, "user")
    assert skill is None
    assert needle in issue.message


def test_no_frontmatter_block(tmp_path: Path):
    d = tmp_path / "plain"
    d.mkdir()
    (d / "SKILL.md").write_text("# just markdown\n")
    skill, issue = frontmatter.read_skill(d, "user")
    assert skill is None
    assert "frontmatter" in issue.message


def test_body_strips_frontmatter(tmp_path: Path):
    d = make(tmp_path, "b", "name: b\ndescription: d", "# Title\n\ntext\n")
    assert frontmatter.read_body(d) == "# Title\n\ntext\n"


def test_requires_evaluation():
    env = Environment(
        tools={"Read"}, mcp={"gh"}, which=lambda b: "/x" if b == "ls" else None
    )
    req = frontmatter.parse_requires(
        {"tools": ["Read", "Figma"], "mcp": ["gh", "notion"], "binaries": "ls, ffmpeg"}
    )
    reason = unavailable_reason(req, env)
    assert "missing tools: Figma" in reason
    assert "missing MCP servers: notion" in reason
    assert "missing binaries: ffmpeg" in reason
    assert (
        unavailable_reason(frontmatter.parse_requires({"tools": ["Read"]}), env) is None
    )
    assert unavailable_reason(frontmatter.parse_requires(None), env) is None


def test_precedence_workspace_user_bundled(tmp_path: Path):
    bundled, user, ws = tmp_path / "b", tmp_path / "u", tmp_path / "w"
    for root in (bundled, user, ws / ".dot" / "skills"):
        make(root, "shared", f"name: shared\ndescription: from {root.name}")
    make(bundled, "only-b", "name: only-b\ndescription: bundled only")
    make(user, "only-u", "name: only-u\ndescription: user only")
    idx = SkillRegistry(bundled, user, ws).index(fresh=True)
    assert idx.skills["shared"].source == "workspace"
    assert idx.skills["only-b"].source == "bundled"
    assert idx.skills["only-u"].source == "user"
    assert sum("shadowed" in i.message for i in idx.issues) == 2
    no_ws = SkillRegistry(bundled, user).index(fresh=True)
    assert no_ws.skills["shared"].source == "user"


def test_unavailable_skill_is_listed_with_reason(tmp_path: Path):
    make(
        tmp_path,
        "needs",
        "name: needs\ndescription: d\nrequires: {binaries: [zzz-nope]}",
    )
    skill = SkillRegistry(tmp_path).index(fresh=True).skills["needs"]
    assert skill.available is False
    assert "zzz-nope" in skill.reason


def test_missing_dirs_are_fine(tmp_path: Path):
    reg = SkillRegistry(tmp_path / "nope", tmp_path / "nope2", tmp_path / "nope3")
    assert reg.index(fresh=True).skills == {}


def test_file_jail(tmp_path: Path):
    d = make(tmp_path / "s", "k", "name: k\ndescription: d")
    (d / "ref.md").write_text("one\ntwo\n")
    (d / "sub").mkdir()
    (d / "sub" / "a.txt").write_text("a")
    secret = tmp_path / "secret.txt"
    secret.write_text("top secret")
    (d / "link.txt").symlink_to(secret)
    (d / "dirlink").symlink_to(tmp_path)
    assert "1\tone" in files.read_text(d, "ref.md")
    assert files.read_text(d, "sub/a.txt").startswith("1\ta")
    for bad in (
        "../secret.txt",
        "/etc/passwd",
        "sub/../../secret.txt",
        "link.txt",
        "dirlink/secret.txt",
        "",
        "nope.md",
        "sub",
    ):
        with pytest.raises(files.SkillFileError):
            files.read_text(d, bad)
    listed = files.list_files(d)
    assert "ref.md" in listed
    assert "link.txt" not in listed
    assert "SKILL.md" not in listed
