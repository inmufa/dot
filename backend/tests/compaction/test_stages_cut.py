from backend.sessions.services.compaction import cut, stages
from compaction_helpers import WS, call, msg


def test_think_dropped_only_when_older_than_four_turns():
    rows = []
    seq = 0
    for i in range(6):
        seq += 1
        rows.append(msg(seq, "user", f"q{i}"))
        seq += 1
        rows.append(msg(seq, "assistant", f"<think>secret {i}</think>answer {i}"))
    out = stages.drop_old_think(rows)
    # assistants of turns 0 and 1 have 5 and 4 user turns after them
    assert set(out) == {2, 4}
    assert out[2] == "answer 0"
    assert "secret" not in out[4]


def test_think_unterminated_block_is_cut():
    assert stages.strip_think("hi <think>never closed") == "hi"
    assert stages.strip_think("<think>a</think>b<think>c</think>d") == "bd"


def test_think_stage_is_a_noop_without_think():
    rows = [msg(1, "user", "q"), msg(2, "assistant", "plain")]
    assert stages.drop_old_think(rows) == {}


def _read_turn(seq: int, cid: str, path: str, body: str):
    return [
        msg(seq, "assistant", calls=[call(cid, "Read", file_path=path)]),
        msg(seq + 1, "tool", body, call_id=cid),
    ]


def test_microcompact_keeps_latest_read_of_each_file():
    big = "x" * 500
    rows = [msg(1, "user", "go")]
    rows += _read_turn(2, "c1", f"{WS}/a.py", big)
    rows += _read_turn(4, "c2", f"{WS}/b.py", big)
    rows += _read_turn(6, "c3", "a.py", big + "newer")  # relative path, same file
    out = stages.microcompact(rows, WS)
    assert set(out) == {3}
    assert "a.py" in out[3]
    assert "newer Read" in out[3]


def test_microcompact_ignores_short_results_and_other_tools():
    rows = [msg(1, "user", "go")]
    rows += _read_turn(2, "c1", f"{WS}/a.py", "tiny")
    rows += _read_turn(4, "c2", f"{WS}/a.py", "tiny2")
    rows += [
        msg(6, "assistant", calls=[call("c3", "Grep", pattern="x")]),
        msg(7, "tool", "y" * 900, call_id="c3"),
        msg(8, "assistant", calls=[call("c4", "Grep", pattern="x")]),
        msg(9, "tool", "y" * 900, call_id="c4"),
    ]
    assert stages.microcompact(rows, WS) == {}


def test_microcompact_is_idempotent():
    big = "x" * 500
    rows = [msg(1, "user", "go")]
    rows += _read_turn(2, "c1", f"{WS}/a.py", big)
    rows += _read_turn(4, "c2", f"{WS}/a.py", big)
    first = stages.microcompact(rows, WS)
    rows[2].view_content = first[3]
    assert stages.microcompact(rows, WS) == {}


def _convo():
    return [
        msg(1, "user", "u1" * 50),
        msg(
            2,
            "assistant",
            calls=[call("a", "Read", file_path="/f"), call("b", "Glob", pattern="*")],
        ),
        msg(3, "tool", "r" * 200, call_id="a"),
        msg(4, "tool", "g" * 200, call_id="b"),
        msg(5, "assistant", "ok" * 50),
        msg(6, "user", "u2" * 50),
        msg(7, "assistant", calls=[call("c", "Read", file_path="/g")]),
        msg(8, "tool", "r" * 200, call_id="c"),
        msg(9, "assistant", "done" * 20),
    ]


def test_cut_never_splits_a_tool_call_from_its_results():
    rows = _convo()
    for keep in range(0, 600, 7):
        i = cut.choose_cut(rows, keep)
        if i is None:
            continue
        assert rows[i].role in ("user", "assistant")
        head = rows[:i]
        ids = {c["id"] for r in head for c in r.tool_calls or []}
        answered = {r.tool_call_id for r in head if r.role == "tool"}
        assert ids == answered, (keep, i)


def test_cut_keeps_tail_within_budget_when_possible():
    rows = _convo()
    i = cut.choose_cut(rows, 130)
    assert i is not None
    assert rows[i].seq in (6, 7, 9)


def test_cut_none_when_nothing_to_summarise():
    assert cut.choose_cut([msg(1, "user", "hi")], 10) is None
    assert cut.choose_cut([msg(1, "summary", "s"), msg(2, "user", "hi")], 5) is None
    # an assistant tool_calls row is open until its result: no cut inside it
    rows = [
        msg(1, "user", "q"),
        msg(2, "assistant", calls=[call("a", "Read", file_path="/f")]),
        msg(3, "tool", "r", call_id="a"),
    ]
    assert cut.choose_cut(rows, 1) == 1  # before the assistant row, never between
