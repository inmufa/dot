import pytest
from backend.routing.clients.scripted import ScriptedLLM
from backend.settings import Settings


@pytest.fixture
def settings(settings: Settings) -> Settings:
    # threshold 75% of 7200 = 5400 tokens (prefix grew with the widget tools, then with
    # the host-mode/browser tool rules, then with core Memory tools + rules, then with the tool-choice guide)
    return settings.model_copy(update={"llm_context_limit": 7200})


@pytest.fixture
def llm() -> ScriptedLLM:
    out = ScriptedLLM([], ["SUMMARY-ONE"] * 5)
    out.realistic_usage = True
    return out
