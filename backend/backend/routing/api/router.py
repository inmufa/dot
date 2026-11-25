from dot_contracts.ui.telemetry import ModelInfo, ModelSelectIn, Telemetry
from fastapi import Request

from backend.core.api.auth import protected_router
from backend.routing.services.telemetry import TelemetryService

router = protected_router(prefix="/v1", tags=["telemetry"])


def service(request: Request) -> TelemetryService:
    return request.app.state.telemetry


@router.get("/telemetry")
async def telemetry(request: Request) -> Telemetry:
    return await service(request).telemetry()


@router.get("/models")
async def models(request: Request) -> list[ModelInfo]:
    return await service(request).models()


@router.post("/models/select")
async def select_model(request: Request, body: ModelSelectIn) -> ModelInfo:
    return await service(request).select(body.name)
