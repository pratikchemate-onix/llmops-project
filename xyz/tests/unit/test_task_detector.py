import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from app.services.task_detector import detect


@pytest.fixture
def mock_vertex_ai():
    """Mock vertexai using sys.modules."""
    mock_vertex_module = MagicMock()
    mock_gen_models_module = MagicMock()
    mock_model_instance = MagicMock()

    mock_gen_models_module.GenerativeModel.return_value = mock_model_instance

    # We need to mock both 'vertexai' and 'vertexai.generative_models'
    with patch.dict(
        sys.modules,
        {"vertexai": mock_vertex_module, "vertexai.generative_models": mock_gen_models_module},
    ):
        yield mock_model_instance


@pytest.fixture(autouse=True)
def reset_global_classifier():
    """Reset the global classifier model before each test to prevent stale mocks."""
    import app.services.task_detector

    app.services.task_detector._CLASSIFIER_MODEL = None
    yield
    app.services.task_detector._CLASSIFIER_MODEL = None


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
def test_detect_parses_llm_response(mock_vertex_ai, llm_response, expected_rag, expected_agent):
    """Verify that the task detector correctly parses various LLM responses."""
    # Mock the response object
    mock_response = MagicMock()
    mock_response.text = llm_response
    mock_vertex_ai.generate_content.return_value = mock_response

    result = detect("some user input", "mock-model")
    assert result["needs_rag"] == expected_rag
    assert result["needs_agent"] == expected_agent


@patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"})
def test_detect_llm_failure_returns_fallback(mock_vertex_ai):
    """Verify that if the LLM call fails, the detector returns a default fallback."""
    mock_vertex_ai.generate_content.side_effect = Exception("API error")
    result = detect("some user input", "mock-model")
    assert result["needs_rag"] is False
    assert result["needs_agent"] is False


@patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"})
def test_detect_json_parsing_error_returns_fallback(mock_vertex_ai):
    """Verify that a JSON parsing error in the LLM response leads to a fallback."""
    mock_response = MagicMock()
    mock_response.text = '{"invalid_json": true'
    mock_vertex_ai.generate_content.return_value = mock_response

    result = detect("some user input", "mock-model")
    assert result["needs_rag"] is False
    assert result["needs_agent"] is False
