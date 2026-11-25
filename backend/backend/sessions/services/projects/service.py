"""Project folders. DOT.md is written by the API only, through the sandbox."""

import re

from dot_contracts.ui.files import Project
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.core.exceptions import DomainException
from backend.core.text import strip_control_tags
from backend.routing.clients.sandbox_client import SandboxClient
from backend.sessions.models import Session

PROJECT_NOT_FOUND = 2033
PROJECT_EXISTS = 2034
ROOT_DIR = "projects"
API_SESSION = "projects-api"  # sandbox session id of backend-initiated writes
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_NO_DOTS = re.compile(r"\.\.")


def valid_name(name: str) -> bool:
    return bool(NAME.match(name)) and not _NO_DOTS.search(name)


class ProjectService:
    def __init__(
        self, maker: async_sessionmaker, sandbox: SandboxClient, workspace: str
    ) -> None:
        self._maker = maker
        self._sandbox = sandbox
        self._root = workspace.rstrip("/")

    def folder(self, name: str) -> str:
        return f"{self._root}/{ROOT_DIR}/{name}"

    def _checked(self, name: str) -> str:
        if not valid_name(name):
            raise DomainException(PROJECT_NOT_FOUND)
        return name

    async def _peek(self, name: str) -> tuple[bool, str]:
        r = await self._sandbox.post(
            API_SESSION, "/internal/peek", {"path": f"{self.folder(name)}/DOT.md"}
        )
        content = r.data.get("content")
        exists = bool(r.ok and r.data.get("exists"))
        return exists, content if isinstance(content, str) else ""

    async def _write(self, name: str, text: str) -> None:
        path = f"{self.folder(name)}/DOT.md"
        exists, _ = await self._peek(name)
        if exists:  # the sandbox wants a read before it overwrites
            await self._sandbox.post(API_SESSION, "/fs/read", {"path": path})
        r = await self._sandbox.post(
            API_SESSION, "/fs/write", {"path": path, "content": text}
        )
        if not r.ok:
            raise DomainException(PROJECT_NOT_FOUND)

    async def _count(self, name: str) -> int:
        async with self._maker() as db:
            q = select(func.count()).select_from(Session).where(Session.project == name)
            return int((await db.scalar(q)) or 0)

    async def _view(self, name: str) -> Project:
        _, text = await self._peek(name)
        return Project(
            name=name,
            path=self.folder(name),
            instructions=text or None,
            sessions=await self._count(name),
        )

    async def names(self) -> list[str]:
        r = await self._sandbox.post(
            API_SESSION,
            "/fs/glob",
            {"pattern": "*/DOT.md", "path": f"{self._root}/{ROOT_DIR}"},
        )
        if not r.ok:
            return []
        prefix = f"{self._root}/{ROOT_DIR}/"
        found = [
            p[len(prefix) :].split("/", 1)[0]
            for p in r.data.get("paths", [])
            if p.startswith(prefix)
        ]
        return sorted({n for n in found if valid_name(n)})

    async def list_all(self) -> list[Project]:
        return [await self._view(n) for n in await self.names()]

    async def create(self, name: str, instructions: str | None) -> Project:
        if name in await self.names():
            raise DomainException(PROJECT_EXISTS)
        await self._write(self._checked(name), instructions or "")
        return await self._view(name)

    async def update(self, name: str, instructions: str) -> Project:
        if self._checked(name) not in await self.names():
            raise DomainException(PROJECT_NOT_FOUND)
        await self._write(name, instructions)
        return await self._view(name)

    async def exists(self, name: str) -> bool:
        return valid_name(name) and name in await self.names()

    async def reminder(self, name: str) -> str:
        """Per-turn note: where this project's files live."""
        if not valid_name(name):
            return ""
        return (
            "<system-reminder>\n"
            f"Project: {strip_control_tags(name)}. Keep this task's files in "
            f"{self.folder(name)} (create it if missing); its DOT.md holds the "
            "project instructions.\n</system-reminder>"
        )
