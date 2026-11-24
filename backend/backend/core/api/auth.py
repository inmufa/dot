import secrets

from fastapi import APIRouter, Depends, Request

from backend.core.exceptions import DomainException

TOKEN_MISSING = 1001


async def require_token(request: Request) -> None:
    """Bearer-token guard. Constant-time compare against DOT_API_TOKEN."""
    scheme, _, supplied = request.headers.get("authorization", "").partition(" ")
    expected = request.app.state.settings.api_token
    if scheme.lower() != "bearer" or not secrets.compare_digest(
        supplied.strip().encode(), expected.encode()
    ):
        raise DomainException(TOKEN_MISSING)


def protected_router(**kwargs) -> APIRouter:
    """Router whose every route needs the bearer token. /health and /ready stay open."""
    return APIRouter(dependencies=[Depends(require_token)], **kwargs)
