"""Read-only view of the llama server, sandbox and GPU (F8)."""

import logging
import time
from pathlib import Path
from typing import Any

import httpx
from dot_contracts.ui.telemetry import ModelInfo, SlotInfo, Telemetry

from backend.core.exceptions import DomainException
from backend.routing.clients.sandbox_client import SandboxClient
from backend.routing.services.registry import ModelEntry, load_registry
from backend.settings import Settings
from backend.voice.client import VoiceClient

logger = logging.getLogger(__name__)
MODEL_UNKNOWN = 4121
SWITCH_UNSUPPORTED = 4120
TELEMETRY_UNAVAILABLE = 4122
_MB = 1024 * 1024


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _num(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return round(float(value), 1)


def read_vram(sysfs: Path | None) -> tuple[int | None, int | None]:
    """(used, total) in MB from mem_info_vram_* files; None when unreadable."""
    if sysfs is None:
        return None, None
    out: list[int | None] = []
    for name in ("mem_info_vram_used", "mem_info_vram_total"):
        try:
            out.append(int((sysfs / name).read_text().strip()) // _MB)
        except (OSError, ValueError):
            out.append(None)
    return out[0], out[1]


def props_vision(props: dict[str, Any]) -> bool:
    """True when llama /props reports the projector loaded (modalities.vision)."""
    mods = props.get("modalities")
    return isinstance(mods, dict) and mods.get("vision") is True


class TelemetryService:
    def __init__(
        self,
        settings: Settings,
        sandbox: SandboxClient,
        client: httpx.AsyncClient | None = None,
        voice: VoiceClient | None = None,
    ) -> None:
        self._voice = voice
        self._s = settings
        self._sandbox = sandbox
        self._root = settings.llm_base_url.rstrip("/").removesuffix("/v1")
        self._http = client or httpx.AsyncClient(
            timeout=httpx.Timeout(3.0), trust_env=False
        )
        self._started = time.monotonic()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _get(self, path: str) -> Any:
        try:
            r = await self._http.get(f"{self._root}{path}")
            return r.json() if r.status_code == httpx.codes.OK else None
        except (httpx.HTTPError, ValueError):
            return None

    async def props(self) -> dict[str, Any]:
        data = await self._get("/props")
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _slots(raw: Any) -> tuple[list[SlotInfo], float | None]:
        slots: list[SlotInfo] = []
        speed: float | None = None
        for item in raw if isinstance(raw, list) else []:
            if not isinstance(item, dict):
                continue
            slots.append(
                SlotInfo(
                    id=_int(item.get("id")) or 0,
                    busy=bool(item.get("is_processing")),
                    context_used=_int(item.get("n_past")) or _int(item.get("n_tokens")),
                    context_size=_int(item.get("n_ctx")),
                )
            )
            timings = item.get("timings")
            if isinstance(timings, dict):
                speed = _num(timings.get("predicted_per_second")) or speed
        return slots, speed

    async def telemetry(self) -> Telemetry:
        up = await self._get("/health") is not None
        props = await self.props() if up else {}
        slots, speed = self._slots(await self._get("/slots") if up else None)
        gen = props.get("default_generation_settings")
        caps = props.get("chat_template_caps")
        levels = caps.get("reasoning_effort_levels") if isinstance(caps, dict) else None
        used, total = read_vram(self._s.vram_sysfs)
        model = props.get("model_path") or props.get("model_alias")
        return Telemetry(
            llm_up=up,
            model=Path(str(model)).name if model else None,
            context_size=_int(gen.get("n_ctx")) if isinstance(gen, dict) else None,
            slots=slots,
            tokens_per_s=speed or None,
            vram_used_mb=used,
            vram_total_mb=total,
            sandbox_up=await self._sandbox.health(),
            voice_up=bool(self._voice and (await self._voice.status())["available"]),
            uptime_s=round(time.monotonic() - self._started, 1),
            reasoning_effort_levels=(
                [str(x) for x in levels][:16] if isinstance(levels, list) else None
            ),
            vision=props_vision(props),
        )

    def _files(self) -> list[Path]:
        try:
            found = sorted(self._s.models_dir.glob("*.gguf"))
        except OSError:
            return []
        return [p for p in found if p.is_file() and not p.name.startswith("mmproj")]

    def _registry(self) -> dict[str, ModelEntry]:
        path = self._s.llm_registry_path or self._s.models_dir / "registry.toml"
        return load_registry(path)

    async def models(self) -> list[ModelInfo]:
        active = Path(str((await self.props()).get("model_path") or "")).name
        reg = self._registry()
        out: list[ModelInfo] = []
        for p in self._files():
            e = reg.get(p.name)
            out.append(
                ModelInfo(
                    name=p.name,
                    size_mb=p.stat().st_size // _MB,
                    active=p.name == active,
                    vision=bool(
                        e
                        and e.vision
                        and (self._s.models_dir / str(e.mmproj)).is_file()
                    ),
                    display_name=e.name if e else None,
                    listed=e is not None,
                    context_max=e.context_max if e else None,
                    thinking=e.thinking if e else False,
                    effort_levels=list(e.effort_levels) if e else [],
                    recommended_profile=e.recommended_profile if e else None,
                    switch_command=f"make model NAME={p.name}",
                )
            )
        return out

    async def select(self, name: str) -> ModelInfo:
        """No in-app switching: the backend has no docker socket (see docs/operations.md)."""
        if name not in {m.name for m in await self.models()}:
            raise DomainException(MODEL_UNKNOWN)
        raise DomainException(SWITCH_UNSUPPORTED)
