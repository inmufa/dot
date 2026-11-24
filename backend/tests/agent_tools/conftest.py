import pytest
from agent_helpers import RoutedLLM


@pytest.fixture
def llm() -> RoutedLLM:
    return RoutedLLM([])
