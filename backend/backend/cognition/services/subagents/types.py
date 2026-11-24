"""Subagent types: toolset and a short system prompt tuned for a small model."""

from dataclasses import dataclass

MAX_DEPTH = 2
MAX_ITERATIONS = 15
MAX_PROMPT_CHARS = 12_000
REPORT_MAX_CHARS = 1600  # about 400 tokens

_RULES = (
    "Work alone on the task you were given. Use tools to look things up; "
    "never guess. Stop as soon as you can answer. Your final message is the "
    "only thing the caller sees: make it a short report (under 300 words) with "
    "the answer, file paths and line numbers. No preamble."
)
_LOCAL = ("Read", "Glob", "Grep", "Skill")
_WEB = ("WebSearch", "WebFetch")
# Deferred in the main agent; a child has no ToolSearch, so it gets them loaded.
BROWSER_TOOLS = ("BrowserNavigate", "BrowserRead", "BrowserClick", "BrowserType")
_EXCLUDED = frozenset(
    {"ToolSearch", "AskUserQuestion", "EnterPlanMode", "ExitPlanMode"}
)


@dataclass(frozen=True)
class SubagentType:
    name: str
    prompt: str
    tools: tuple[str, ...] | None  # None: every non-deferred tool except _EXCLUDED
    read_only: bool  # may run concurrently with others
    loaded: tuple[str, ...] = ()  # deferred tools preloaded for this type


TYPES: dict[str, SubagentType] = {
    "Explore": SubagentType(
        "Explore",
        "You are Explore, a read-only code search agent. Find files and facts "
        "with Glob, Grep and Read. You cannot change anything.\n" + _RULES,
        (*_LOCAL, *_WEB),
        read_only=True,
    ),
    "Plan": SubagentType(
        "Plan",
        "You are Plan, a read-only planning agent. Read the relevant code, then "
        "write a numbered step-by-step plan with file paths. You cannot change "
        "anything.\n" + _RULES,
        (*_LOCAL, *_WEB),
        read_only=True,
    ),
    "general-purpose": SubagentType(
        "general-purpose",
        "You are a general-purpose agent. Do the task end to end with the tools "
        "available: read before you edit, verify with real command output.\n" + _RULES,
        None,
        read_only=False,
        loaded=BROWSER_TOOLS,
    ),
    "Verifier": SubagentType(
        "Verifier",
        "You are Verifier. Run the tests or the program with Bash and check the "
        "real output. Do not edit files. Report PASS or FAIL with the evidence "
        "(command, exit code, key output lines).\n" + _RULES,
        (*_LOCAL, "Bash", "BashOutput", "KillShell"),
        read_only=False,
    ),
}


def tool_names(kind: SubagentType, all_core: list[str]) -> list[str]:
    if kind.tools is None:
        return [n for n in all_core if n not in _EXCLUDED]
    return [n for n in all_core if n in kind.tools]


def clip_report(text: str) -> str:
    text = text.strip() or "(the subagent returned no report)"
    if len(text) <= REPORT_MAX_CHARS:
        return text
    return text[:REPORT_MAX_CHARS] + "\n... [report truncated]"
