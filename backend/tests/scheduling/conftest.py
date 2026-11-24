import pytest
from backend.settings import Settings


@pytest.fixture
def settings(settings: Settings) -> Settings:
    # Tests drive their own Scheduler with a fake clock.
    return settings.model_copy(update={"scheduler_enabled": False})
