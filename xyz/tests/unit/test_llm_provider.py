import os
from unittest.mock import MagicMock, patch

import litellm
import pytest

import app.services.llm_provider as provider


@pytest.fixture(autouse=True)
def reset_globals():
    """Reset the global initialization state before each test."""
    provider._VERTEXAI_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    provider._VERTEXAI_LOCATION = os.getenv("VERTEXAI_LOCATION", "us-central1")
    yield

@pytest.fixture
def mock_litellm():
    """Mock the litellm completion call."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "litellm response"

    with patch("app.services.llm_provider.litellm.completion") as mock_completion:
        mock_completion.return_value = mock_response
        yield mock_completion

def test_generate_mock_returns_mock_response():
    """Verify that the mock model returns the expected mock response."""
    prompt = "Hello, world!"
    model = "mock"
    response = provider.generate(prompt, model)
    assert "[MOCK RESPONSE]" in response
    assert prompt[:80] in response

@patch.dict(
    os.environ,
    {"GOOGLE_CLOUD_PROJECT": "test-project"},
)
def test_generate_gemini_model_succeeds(mock_litellm):
    """Test that the Gemini provider can be called successfully via litellm."""
    provider._VERTEXAI_PROJECT = "test-project"

    response = provider.generate("test prompt", "gemini-2.5-flash")

    assert response == "litellm response"
    mock_litellm.assert_called_with(
        model="vertex_ai/gemini-2.5-flash",
        messages=[{"role": "user", "content": "test prompt"}],
        temperature=0.2,
        max_tokens=2048,
    )

@patch.dict(os.environ, {}, clear=True)
def test_generate_gemini_missing_project_id_raises_runtime_error(mock_litellm):
    """Verify that a missing Google Cloud project ID raises a RuntimeError for Gemini."""
    provider._VERTEXAI_PROJECT = ""

    with pytest.raises(
        RuntimeError, match="GOOGLE_CLOUD_PROJECT environment variable is not set"
    ):
        provider.generate("test prompt", "gemini-2.5-flash")

@patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
def test_generate_claude_model_succeeds(mock_litellm):
    """Test that the Claude provider can be called successfully via litellm."""
    response = provider.generate("test prompt", "claude-3-opus-20240229")

    assert response == "litellm response"
    mock_litellm.assert_called_with(
        model="claude-3-opus-20240229",
        messages=[{"role": "user", "content": "test prompt"}],
        temperature=0.2,
        max_tokens=2048,
    )

def test_generate_authentication_error():
    """Test that an AuthenticationError is handled correctly."""
    with patch("app.services.llm_provider.litellm.completion") as mock_completion:
        # litellm 1.0.0+ requires model, message and llm_provider
        mock_completion.side_effect = litellm.AuthenticationError(message="invalid x-api-key", llm_provider="anthropic", model="claude-3-opus")

        with pytest.raises(RuntimeError, match="Authentication failed for claude"):
            provider.generate("test prompt", "claude-3-opus-20240229")

def test_generate_general_exception():
    """Test that a general Exception is handled correctly."""
    with patch("app.services.llm_provider.litellm.completion") as mock_completion:
        mock_completion.side_effect = Exception("General API error")

        with pytest.raises(RuntimeError, match="LLM call failed for claude"):
            provider.generate("test prompt", "claude-3-opus-20240229")
