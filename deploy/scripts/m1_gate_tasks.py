"""Tool schemas and the 20 scripted tasks for m1_model_gate.py."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _tool(name: str, props: dict[str, str], required: list[str]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": f"{name} tool",
            "parameters": {
                "type": "object",
                "properties": {k: {"type": v} for k, v in props.items()},
                "required": required,
            },
        },
    }


TOOLS = [
    _tool("Read", {"path": "string", "offset": "integer"}, ["path"]),
    _tool("Write", {"path": "string", "content": "string"}, ["path", "content"]),
    _tool(
        "Edit",
        {"path": "string", "old": "string", "new": "string"},
        ["path", "old", "new"],
    ),
    _tool("Bash", {"command": "string"}, ["command"]),
    _tool("Grep", {"pattern": "string", "path": "string"}, ["pattern"]),
    _tool("Glob", {"pattern": "string"}, ["pattern"]),
    _tool("WebSearch", {"query": "string"}, ["query"]),
    _tool("WebFetch", {"url": "string"}, ["url"]),
]


@dataclass(frozen=True)
class Task:
    prompt: str
    tool: str
    arg: str | None = None
    pattern: str = ""
    # Other tools that are also a correct first step (e.g. Read before Edit).
    also: tuple[str, ...] = ()


TASKS = [
    Task("Show me the file /workspace/app/main.py", "Read", "path", r"main\.py"),
    Task(
        "Open /workspace/README.md and tell me what it says", "Read", "path", r"README"
    ),
    Task(
        "Read lines starting at 100 of /workspace/big.log", "Read", "path", r"big\.log"
    ),
    Task("Run the test suite with pytest", "Bash", "command", r"pytest"),
    Task("List the files in the current directory", "Bash", "command", r"\bls\b"),
    Task("Check the git status", "Bash", "command", r"git status"),
    Task("Install the dependencies with uv sync", "Bash", "command", r"uv sync"),
    Task("Find every TODO in the codebase", "Grep", "pattern", r"TODO"),
    Task("Search the code for the string 'def main'", "Grep", "pattern", r"def main"),
    Task("Find all python files under /workspace", "Glob", "pattern", r"\.py"),
    Task("List every markdown file", "Glob", "pattern", r"\.md"),
    Task(
        "Create /workspace/hello.py that prints hello",
        "Write",
        "path",
        r"hello\.py",
    ),
    Task(
        "Write a .gitignore file at /workspace/.gitignore",
        "Write",
        "path",
        r"gitignore",
    ),
    Task(
        "In /workspace/app.py replace the text 'foo' with 'bar'",
        "Edit",
        "path",
        r"app\.py",
    ),
    Task(
        "Rename the variable x to count in /workspace/calc.py",
        "Edit",
        "path",
        r"calc\.py",
        ("Read",),
    ),
    Task(
        "Search the web for the latest llama.cpp release",
        "WebSearch",
        "query",
        r"llama",
    ),
    Task("Look up the Python 3.12 release date online", "WebSearch", "query", r"3\.12"),
    Task(
        "Fetch https://example.com/docs and read it", "WebFetch", "url", r"example\.com"
    ),
    Task(
        "Download the page at https://example.org/a", "WebFetch", "url", r"example\.org"
    ),
    Task("Count lines of all python files with wc", "Bash", "command", r"wc"),
]
