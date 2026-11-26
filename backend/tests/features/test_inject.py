import pytest
from backend.cognition.services.engine.effort.profiles import PROFILES
from backend.cognition.services.engine.tool_runner import _dealias_workspace, _loop_note
from backend.cognition.services.engine.turn import Turn
from backend.cognition.services.widgets.present_tool import (
    WidgetError,
    validate_present,
)
from dot_contracts.tools import ToolResult
from dot_contracts.ui.effort import Effort
from helpers import new_session
from httpx import AsyncClient


async def test_inject_without_running_turn_is_not_queued(authed: AsyncClient):
    sid = await new_session(authed, "default")
    r = await authed.post(f"/v1/sessions/{sid}/inject", json={"message": "hi"})
    assert r.json() == {"queued": False}
    r = await authed.post(f"/v1/sessions/{sid}/inject/cancel", json={"message": "hi"})
    assert r.json() == {"removed": False}


def test_third_identical_failure_tells_the_model_to_stop():
    turn = Turn(pk=1, public_id="S1")
    res = ToolResult(call_id="c", output="boom", is_error=True)
    out = [_loop_note(turn, "Bash", {"command": "x"}, res).output for _ in range(3)]
    assert out[0] == out[1] == "boom"
    assert "Stop retrying" in out[2]
    fresh = Turn(pk=2, public_id="S2")
    assert _loop_note(fresh, "Bash", {"command": "y"}, res).output == "boom"


def test_one_tool_failing_with_varied_args_also_trips_the_guard():
    turn = Turn(pk=1, public_id="S1")
    res = ToolResult(call_id="c", output="bad", is_error=True)
    outs = [_loop_note(turn, "Present", {"n": i}, res).output for i in range(4)]
    assert outs[:3] == ["bad"] * 3
    assert "keeps failing" in outs[3]
    ok = ToolResult(call_id="c", output="fine")
    _loop_note(turn, "Present", {"n": 9}, ok)
    assert _loop_note(turn, "Present", {"n": 10}, res).output == "bad"


def test_table_accepts_wrapped_columns_and_errors_show_an_example():
    ok = {"kind": "table", "props": {"columns": [["A"], ["B"]], "rows": [["1", "2"]]}}
    assert validate_present(ok)[2]["columns"] == ["A", "B"]
    bad = {"kind": "table", "props": {"columns": ["A"], "rows": [["1", "2"]]}}
    with pytest.raises(WidgetError, match="Correct shape"):
        validate_present(bad)


def test_failed_result_marks_the_turn_for_a_short_think_cap():
    turn = Turn(pk=1, public_id="S1")
    _loop_note(turn, "Bash", {}, ToolResult(call_id="c", output="x", is_error=True))
    assert turn.last_failed
    _loop_note(turn, "Bash", {}, ToolResult(call_id="c", output="ok"))
    assert not turn.last_failed
    assert PROFILES[Effort.MEDIUM].think_cap == 4000


def test_identical_successful_result_also_trips_a_loop_note():
    turn = Turn(pk=1, public_id="S1")
    res = ToolResult(call_id="c", output="Went back.\nPage: about:blank")
    outs = [
        _loop_note(turn, "BrowserNavigate", {"back": True}, res).output
        for _ in range(3)
    ]
    assert outs[:2] == [res.output] * 2
    assert "same result with no progress" in outs[2]
    assert not turn.last_failed
    # the streak counts identical arguments, not identical output: a real page (Google's
    # sign-in, for one) embeds a random token in every response, so comparing output text
    # would never catch this loop
    turn2 = Turn(pk=2, public_id="S2")
    _loop_note(turn2, "BrowserNavigate", {"back": True}, res)
    _loop_note(
        turn2,
        "BrowserNavigate",
        {"back": True},
        ToolResult(call_id="c", output="Went back.\nPage: real"),
    )
    assert (
        "same result with no progress"
        in _loop_note(turn2, "BrowserNavigate", {"back": True}, res).output
    )


def test_workspace_alias_is_rewritten_to_the_real_root():
    out = _dealias_workspace(
        {"file_path": "/workspace/notes.txt", "content": "x"}, "/home/u/ws"
    )
    assert out["file_path"] == "/home/u/ws/notes.txt"
    assert out["content"] == "x"
    same = {"file_path": "/elsewhere/notes.txt"}
    assert _dealias_workspace(same, "/home/u/ws") is same
