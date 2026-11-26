"""Request and response bodies."""

from typing import Literal

from pydantic import BaseModel, Field


class ReadIn(BaseModel):
    path: str
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=2000, ge=1)


class ReadOut(BaseModel):
    content: str
    total_lines: int
    numbered: bool = True


class WriteIn(BaseModel):
    path: str
    content: str


class WriteOut(BaseModel):
    path: str
    created: bool


class EditOp(BaseModel):
    old: str
    new: str
    replace_all: bool = False


class EditIn(BaseModel):
    path: str
    old: str = ""
    new: str = ""
    replace_all: bool = False
    edits: list[EditOp] | None = Field(default=None, max_length=50)  # several, atomic


class EditOut(BaseModel):
    path: str
    replacements: int
    lint: str | None = None


class GlobIn(BaseModel):
    pattern: str
    path: str | None = None


class GlobOut(BaseModel):
    paths: list[str]


class GrepIn(BaseModel):
    pattern: str
    path: str | None = None
    glob: str | None = None
    output_mode: Literal["files_with_matches", "content", "count"] = (
        "files_with_matches"
    )
    context: int = Field(default=0, ge=0, le=20)
    ignore_case: bool = False
    head_limit: int = Field(default=250, ge=1)


class GrepOut(BaseModel):
    output: str


class ExecIn(BaseModel):
    command: str
    stdin: str | None = Field(default=None, max_length=1_000_000)
    timeout_s: float = Field(default=120, gt=0, le=3600)
    cwd: str | None = None
    background: bool = False


class ExecOut(BaseModel):
    stdout: str
    stderr: str
    exit_code: int | None
    timed_out: bool
    truncated: bool
    spill_path: str | None
    shell_id: str | None


class ShellIn(BaseModel):
    shell_id: str


class ShellOutput(BaseModel):
    stdout: str
    stderr: str
    running: bool
    exit_code: int | None


class Ok(BaseModel):
    ok: bool = True


class CheckpointIn(BaseModel):
    path: str


class CheckpointOut(BaseModel):
    checkpoint_id: str
    existed: bool


class RestoreIn(BaseModel):
    checkpoint_id: str
    dry_run: bool = False


class RestoreOut(BaseModel):
    path: str
    action: str


class PeekIn(BaseModel):
    path: str


class PeekOut(BaseModel):
    exists: bool
    content: str | None = None


class RealpathIn(BaseModel):
    path: str


class RealpathOut(BaseModel):
    path: str  # symlinks resolved
    inside: bool  # still within the workspace


class BinariesIn(BaseModel):
    names: list[str] = Field(max_length=64)


class BinariesOut(BaseModel):
    found: list[str]
