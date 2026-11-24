import pytest
from backend.routing.clients.scripted import ScriptedLLM
from backend.settings import Settings


@pytest.fixture
def settings(settings: Settings) -> Settings:
    # threshold 75% of 4000 = 3000 tokens
    return settings.model_copy(update={"llm_context_limit": 4000})


@pytest.fixture
def llm() -> ScriptedLLM:
    out = ScriptedLLM([], ["SUMMARY-ONE"] * 5)
    out.realistic_usage = True
    return out
