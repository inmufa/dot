"""Attachments, session files, workspace tree and projects (F3, F4, F7)."""

from typing import Literal

from pydantic import BaseModel, Field

from dot_contracts.types import UtcDatetime

AttachmentKind = Literal["image", "document", "text", "data"]


class Attachment(BaseModel):
    id: str
    session_id: str
    name: str
    mime: str
    size: int
    kind: AttachmentKind
    path: str  # absolute workspace path, under uploads/<session>/
    pages: int | None = None  # PDF pages
    extracted_chars: int | None = None  # text pulled from pdf/docx/xlsx
    width: int | None = None  # images
    height: int | None = None
    created_at: UtcDatetime


class FileInfo(BaseModel):
    path: str  # absolute workspace path
    name: str
    size: int
    mime: str
    origin: Literal["created", "modified", "upload"]
    modified_at: UtcDatetime
    seq: int | None = None  # transcript seq of the tool call that wrote it


class TreeEntry(BaseModel):
    path: str
    name: str
    type: Literal["dir", "file"]
    size: int | None = None
    modified_at: UtcDatetime | None = None


class Project(BaseModel):
    name: str
    path: str  # absolute workspace folder
    instructions: str | None = None  # DOT.md content
    sessions: int = 0


class ProjectIn(BaseModel):
    name: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
    instructions: str | None = Field(default=None, max_length=20_000)


class ProjectPatch(BaseModel):
    instructions: str = Field(max_length=20_000)
