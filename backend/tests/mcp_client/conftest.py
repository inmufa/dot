import pytest
from backend.settings import Settings


@pytest.fixture
def settings(settings: Settings) -> Settings:
    return settings.model_copy(
        update={
            "mcp_reconcile_interval_s": 0.2,
            "mcp_ping_interval_s": 0.5,
            "mcp_call_timeout_s": 5.0,
            "mcp_connect_timeout_s": 15.0,
        }
    )
