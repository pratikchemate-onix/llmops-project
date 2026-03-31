import os
from unittest.mock import patch

import pytest

from app.services.task_detector import detect


@pytest.fixture
def mock_llm_provider():
    """Mock llm_provider.generate."""
    with patch("app.services.llm_provider.generate") as mock_generate:
        yield mock_generate

@pytest.mark.parametrize(
    ("llm_response, expected_rag, expected_agent"),
    [
        ("NEEDS_RAG", True, False),
        ("NEEDS_AGENT", False, True),
        ('{"needs_rag": true, "needs_agent": false}', True, False),
        ('{"needs_agent": true, "needs_rag": false}', False, True),
        ("Something else", False, False),
        ("", False, False),
    ],
)
@patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"})
def test_detect_parses_llm_response(
    mock_llm_provider, llm_response, expected_rag, expected_agent
):
    """Verify that the task detector correctly parses various LLM responses."""
    mock_llm_provider.return_value = llm_response

    result = detect("some user input", "mock-model")
    assert result["needs_rag"] == expected_rag
    assert result["needs_agent"] == expected_agent


@patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"})
def test_detect_llm_failure_returns_fallback(mock_llm_provider):
    """Verify that if the LLM call fails, the detector returns a default fallback."""
    mock_llm_provider.side_effect = Exception("API error")
    result = detect("some user input", "mock-model")
    assert result["needs_rag"] is False
    assert result["needs_agent"] is False


@patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"})
def test_detect_json_parsing_error_returns_fallback(mock_llm_provider):
    """Verify that a JSON parsing error in the LLM response leads to a fallback."""
    mock_llm_provider.return_value = '{"invalid_json": true'

    result = detect("some user input", "mock-model")
    assert result["needs_rag"] is False
    assert result["needs_agent"] is False
