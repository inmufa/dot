import json
from pathlib import Path

import pytest
from backend.core.exceptions import DomainException
from backend.memory.services import factfile
from backend.memory.services.consolidate import consolidate
from backend.memory.services.embedder import NullEmbedder
from backend.memory.services.store import MemoryService
from backend.routing.clients.scripted import ScriptedLLM
from dot_contracts.memory import MemoryIn, MemoryKind, MemoryUpdate
from fastapi import FastAPI


@pytest.fixture
def mem(app: FastAPI) -> MemoryService:
    return app.state.memory


def fact(name: str, body: str, desc: str = "") -> MemoryIn:
    return MemoryIn(name=name, description=desc, body=body)


async def test_crud_writes_one_file_per_fact_and_an_index(mem: MemoryService):
    a = await mem.add(fact("Editor choice", "The user prefers vim.", "editor"))
    b = await mem.add(
        MemoryIn(
            name="Deploy", body="Deploys go through make up", kind=MemoryKind.PROJECT
        )
    )
    files = sorted(p.name for p in mem.directory.glob("*.md"))
    assert files == ["MEMORY.md", "deploy.md", "editor-choice.md"]
    parsed = factfile.parse((mem.directory / "editor-choice.md").read_text())
    assert parsed
    assert parsed.id == a.id
    assert parsed.body == "The user prefers vim."
    index = (mem.directory / "MEMORY.md").read_text().splitlines()
    assert index == [
        "- [Deploy](deploy.md)",
        "- [Editor choice](editor-choice.md) - editor",
    ]
    up = await mem.update(a.id, MemoryUpdate(body="The user prefers neovim."))
    assert up.body == "The user prefers neovim."
    assert "neovim" in (mem.directory / "editor-choice.md").read_text()
    assert (await mem.get(b.id)).name == "Deploy"
    await mem.delete(b.id)
    assert not (mem.directory / "deploy.md").exists()
    assert [f.id for f in await mem.list_facts()] == [a.id]
    with pytest.raises(DomainException) as exc:
        await mem.get(b.id)
    assert exc.value.code == 2021


async def test_name_collisions_and_hostile_names_stay_inside_the_directory(
    mem: MemoryService,
):
    one = await mem.add(fact("../../etc/passwd", "x"))
    two = await mem.add(fact("../../etc/passwd", "y"))
    names = {p.name for p in mem.directory.glob("*.md")}
    assert {"etc-passwd.md", "etc-passwd-2.md"} <= names
    assert one.id != two.id
    assert not list(mem.directory.parent.glob("etc*"))


async def test_fts_search_ranks_and_updates(mem: MemoryService):
    await mem.add(fact("Python tooling", "Use uv and ruff for python projects"))
    await mem.add(fact("Gardening", "Tomatoes need sun"))
    await mem.add(fact("Python style", "Prefer pathlib over os.path in python code"))
    hits = await mem.search("python ruff")
    assert hits[0].name == "Python tooling"
    assert {h.name for h in hits} == {"Python tooling", "Python style"}
    assert [h.name for h in await mem.search("tomat")] == ["Gardening"]  # prefix match
    assert await mem.search("zzzz") == []
    assert await mem.search("   ") == []
    assert (
        await mem.search('"; DROP TABLE memory_facts; --') == []
    )  # quoted, not executed
    tomato = (await mem.search("tomatoes"))[0]
    await mem.update(tomato.id, MemoryUpdate(body="Basil likes shade"))
    assert await mem.search("tomatoes") == []
    assert [h.name for h in await mem.search("basil")] == ["Gardening"]
    await mem.delete(tomato.id)
    assert await mem.search("basil") == []


async def test_index_text_is_capped_at_200_lines(mem: MemoryService):
    for i in range(205):
        await mem.add(fact(f"fact {i:03d}", f"body {i}"))
    assert len((mem.directory / "MEMORY.md").read_text().splitlines()) == 205
    assert len((await mem.index_text(200)).splitlines()) == 200


async def test_reindex_picks_up_hand_written_files(mem: MemoryService):
    mem.directory.mkdir(parents=True, exist_ok=True)
    (mem.directory / "mine.md").write_text(
        "---\nname: Mine\ndescription: hand made\n---\nzebra facts\n"
    )
    (mem.directory / "junk.md").write_text("no frontmatter")
    assert await mem.reindex() == 1
    (hit,) = await mem.search("zebra")
    assert hit.id.startswith("M")
    assert f"id: {hit.id}" in (mem.directory / "mine.md").read_text()  # id written back
    assert await mem.reindex() == 1
    assert (await mem.search("zebra"))[0].id == hit.id


async def test_consolidation_drops_exact_duplicates_and_merges_via_llm(
    mem: MemoryService,
):
    a = await mem.add(fact("Vim", "User likes vim"))
    await mem.add(fact("Vim again", "user  likes   VIM"))  # exact dup after normalising
    b = await mem.add(fact("Editor", "Uses vim keybindings everywhere"))
    c = await mem.add(fact("Shell", "Uses fish"))
    reply = json.dumps(
        {
            "merges": [
                {
                    "ids": [a.id, b.id],
                    "name": "Editor",
                    "description": "vim",
                    "body": "Likes vim, uses vim keybindings",
                },
                {"ids": [c.id, "MBOGUS0000"], "name": "x", "body": "bad group"},
                {"ids": [c.id], "name": "x", "body": "single"},
            ]
        }
    )
    llm = ScriptedLLM([], ["Sure, here you go: " + reply])
    report = await consolidate(mem, llm)
    assert report.exact_removed == 1
    assert report.merged_groups == 1
    assert report.removed == 2
    names = sorted(f.name for f in await mem.list_facts())
    assert names == ["Editor", "Shell"]
    assert "facts" in llm.complete_requests[0][0]["content"]


async def test_consolidation_ignores_garbage_and_llm_failure(mem: MemoryService):
    await mem.add(fact("One", "alpha"))
    await mem.add(fact("Two", "beta"))
    report = await consolidate(mem, ScriptedLLM([], ["not json at all"]))
    assert (report.merged_groups, report.removed) == (0, 0)
    assert len(await mem.list_facts()) == 2

    class Down(ScriptedLLM):
        async def complete(self, messages, max_tokens=1024):
            raise DomainException(4000)

    assert (await consolidate(mem, Down([]))).merged_groups == 0


async def test_null_embedder_is_inert():
    assert await NullEmbedder().embed(["a", "b"]) == [[], []]


def test_factfile_roundtrip_and_rejects_bad_input():
    f = factfile.FactFile("M1", "Name", "a\nb", "user", "body\ntext")
    parsed = factfile.parse(factfile.render(f))
    assert parsed
    assert parsed.description == "a b"  # frontmatter stays one line
    assert parsed.body == "body\ntext"
    assert factfile.parse("plain") is None
    assert factfile.parse("---\nname: x\nno end") is None
    assert factfile.parse("---\ndescription: y\n---\nb") is None


def test_memory_dir_is_isolated_in_tests(settings, tmp_path: Path):
    assert str(settings.memory_dir).startswith(str(tmp_path))
