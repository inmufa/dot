"""Slash-command registry (F14): server operations, client actions, skills."""

from dot_contracts.ui.commands import CommandArg, CommandEndpoint, CommandInfo

from backend.sessions.models import Message

_SID = "/v1/sessions/{id}"
_LEVELS = ["off", "low", "medium", "high", "max"]


def _server(  # noqa: PLR0913
    name: str,
    description: str,
    group: str,
    method: str,
    path: str,
    *,
    args: list[CommandArg] | None = None,
    stream: bool = False,
    body_arg: str | None = None,
) -> CommandInfo:
    return CommandInfo(
        name=name,
        description=description,
        group=group,  # type: ignore[arg-type]
        args=args or [],
        kind="server",
        endpoint=CommandEndpoint(
            method=method,  # type: ignore[arg-type]
            path=path,
            stream=stream,
            body_arg=body_arg,
        ),
    )


def _client(name: str, description: str, args: list[CommandArg]) -> CommandInfo:
    return CommandInfo(
        name=name, description=description, group="ui", args=args, kind="client"
    )


def server_commands() -> list[CommandInfo]:
    text = CommandArg
    return [
        _server(
            "compact",
            "Summarise older messages to free context",
            "context",
            "POST",
            f"{_SID}/compact",
            args=[text(name="focus", hint="what the summary must keep")],
            body_arg="focus",
        ),
        _server("context", "Show context usage", "context", "GET", f"{_SID}/context"),
        _server(
            "usage", "Tokens, speed and turn timing", "context", "GET", f"{_SID}/usage"
        ),
        _server(
            "clear",
            "Start a fresh session, keep this one",
            "session",
            "POST",
            f"{_SID}/clear",
        ),
        _server(
            "retry",
            "Regenerate the last answer",
            "session",
            "POST",
            f"{_SID}/regenerate",
            stream=True,
        ),
        _server(
            "branch",
            "Branch from a message into a new session",
            "session",
            "POST",
            f"{_SID}/branch",
            args=[text(name="from_seq", hint="message seq; default: the end")],
            body_arg="from_seq",
        ),
        _server(
            "rename",
            "Rename this session",
            "session",
            "PATCH",
            _SID,
            args=[text(name="title", required=True)],
            body_arg="title",
        ),
        _server(
            "export",
            "Download the session",
            "session",
            "GET",
            f"{_SID}/export",
            args=[text(name="format", choices=["md", "json"])],
        ),
        _server("resume", "Pick an earlier session", "session", "GET", "/v1/sessions"),
        _server(
            "btw",
            "Ask a side question; nothing is stored",
            "session",
            "POST",
            f"{_SID}/btw",
            args=[text(name="question", required=True)],
            stream=True,
            body_arg="question",
        ),
        _server(
            "effort",
            "Set how hard the model thinks",
            "model",
            "PATCH",
            _SID,
            args=[text(name="level", required=True, choices=_LEVELS)],
            body_arg="effort",
        ),
        _server(
            "model",
            "Switch the model",
            "model",
            "POST",
            "/v1/models/select",
            args=[text(name="name", required=True)],
            body_arg="name",
        ),
    ]


def client_commands() -> list[CommandInfo]:
    return [
        _client("help", "What Dot can do", []),
        _client("new", "New session", []),
        _client(
            "mode",
            "Change the permission mode",
            [
                CommandArg(
                    name="mode",
                    required=True,
                    choices=["default", "acceptEdits", "plan", "auto", "bypass"],
                )
            ],
        ),
        _client("plan", "Plan first, then act", []),
    ]


def availability(name: str, rows: list[Message]) -> str | None:
    """Why a session-bound command cannot run now (None: available)."""
    answered = any(r.role == "assistant" for r in rows)
    if name in {"retry", "branch", "export", "usage"} and not answered:
        return "no finished turn yet"
    if name == "compact" and not rows:
        return "nothing to compact"
    return None
