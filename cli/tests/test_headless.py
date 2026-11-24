import httpx
from dot_cli.config import Config, parse_config
from dot_cli.headless import run_once
from support import DONE, FakeBackend, sse, tok

TOOL = {"call_id": "c1", "name": "Bash", "arguments": {}}


async def test_once_prints_final_answer(capsys) -> None:
    body = sse(
        tok("hmm", thinking=True),
        tok("draft"),
        {"type": "tool_call", "invocation": TOOL},
        tok("final "),
        tok("answer"),
        DONE,
    )
    backend = FakeBackend(lambda: httpx.Response(200, content=body))
    code = await run_once(Config(once="q"), backend.client())
    assert code == 0
    assert capsys.readouterr().out == "final answer\n"


async def test_once_rejects_approval_and_reports_error(capsys) -> None:
    approval = {"type": "approval_required", "approval_id": "A9", "invocation": TOOL}
    err = {"type": "error", "code": 2001, "message": "busy"}
    backend = FakeBackend(lambda: httpx.Response(200, content=sse(approval, err, DONE)))
    code = await run_once(Config(once="q"), backend.client())
    assert code == 1
    assert "POST /v1/approvals/A9/resolve" in backend.paths()
    assert "busy" in capsys.readouterr().err


def test_config_env_and_args() -> None:
    env = {"DOT_URL": "http://x:1", "DOT_API_TOKEN": "t"}
    cfg = parse_config(["--once", "hi", "--mode", "plan"], env)
    assert (cfg.url, cfg.token, cfg.once, cfg.mode) == ("http://x:1", "t", "hi", "plan")
    assert parse_config([], {}).url == "http://127.0.0.1:8000"


async def test_once_answers_questions_without_hanging(capsys) -> None:
    question = {
        "type": "question",
        "question_id": "Q1",
        "question": "which?",
        "options": [{"label": "a"}, {"label": "b"}],
    }
    sub = {
        "type": "subagent",
        "label": "Explore 1",
        "subagent_type": "Explore",
        "status": "started",
    }
    body = sse(sub, question, tok("ok"), DONE)
    backend = FakeBackend(lambda: httpx.Response(200, content=body))
    assert await run_once(Config(once="q"), backend.client()) == 0
    assert "POST /v1/questions/Q1/answer" in backend.paths()
    assert capsys.readouterr().out == "ok\n"
