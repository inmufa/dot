from types import SimpleNamespace

from backend.cognition.services.tools.diffs import edit_diff
from backend.cognition.services.tools.fs_tools import run_edit
from backend.routing.clients.sandbox_client import SandboxResponse


class Sandbox:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def post(self, _sid: str, _path: str, payload: dict) -> SandboxResponse:
        self.sent.append(payload)
        n = len(payload.get("edits", [])) or 1
        return SandboxResponse(200, {"path": payload["path"], "replacements": n})


def ctx(sb: Sandbox):
    return SimpleNamespace(sandbox=sb, session_id="S1", workspace="/w")


async def test_edits_list_goes_out_as_one_call():
    sb = Sandbox()
    edits = [
        {"old_string": "a", "new_string": "b"},
        {"old_string": "c", "new_string": "d", "replace_all": True},
    ]
    r = await run_edit(ctx(sb), {"file_path": "x.py", "edits": edits})
    assert not r.is_error
    assert "2 replacement" in r.output
    assert sb.sent == [
        {
            "path": "/w/x.py",
            "edits": [
                {"old": "a", "new": "b", "replace_all": False},
                {"old": "c", "new": "d", "replace_all": True},
            ],
        }
    ]


async def test_single_edit_shape_is_unchanged():
    sb = Sandbox()
    await run_edit(ctx(sb), {"file_path": "/a", "old_string": "x", "new_string": "y"})
    assert sb.sent == [{"path": "/a", "old": "x", "new": "y", "replace_all": False}]


async def test_edit_without_strings_is_a_clear_error():
    r = await run_edit(ctx(Sandbox()), {"file_path": "/a"})
    assert r.is_error
    assert "edits list" in r.output


def test_diff_shows_every_edit():
    d = edit_diff(
        {
            "edits": [
                {"old_string": "a", "new_string": "b"},
                {"old_string": "c", "new_string": "d"},
            ]
        }
    )
    assert d == "- a\n+ b\n...\n- c\n+ d"
