import os
import sys
from unittest.mock import MagicMock, patch

import pytest

import app.services.llm_provider as provider


@pytest.fixture(autouse=True)
def reset_vertex_globals():
    """Reset the global initialization state before each test."""
    provider._VERTEXAI_INITIALIZED = False
    # Also reset the project variable to allow re-reading from env
    provider._VERTEXAI_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    # Reset the global model cache
    if hasattr(provider, "_GEMINI_MODELS"):
        provider._GEMINI_MODELS.clear()
    yield
    provider._VERTEXAI_INITIALIZED = False
    if hasattr(provider, "_GEMINI_MODELS"):
        provider._GEMINI_MODELS.clear()


@pytest.fixture
def mock_vertexai():
    """Mock the vertexai library using sys.modules."""
    mock_vertex_module = MagicMock()
    mock_generative_models = MagicMock()
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Gemini response"

    mock_model.generate_content.return_value = mock_response
    mock_generative_models.GenerativeModel.return_value = mock_model
    mock_generative_models.GenerationConfig = MagicMock()

    mock_vertex_module.generative_models = mock_generative_models

    with patch.dict(
        sys.modules,
        {"vertexai": mock_vertex_module, "vertexai.generative_models": mock_generative_models},
    ):
        yield mock_vertex_module


@pytest.fixture
def mock_anthropic():
    """Mock the anthropic library using sys.modules."""
    mock_anthropic_module = MagicMock()
    mock_client = MagicMock()
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="Claude response")]
    mock_client.messages.create.return_value = mock_message

    mock_anthropic_module.Anthropic.return_value = mock_client

    with patch.dict(sys.modules, {"anthropic": mock_anthropic_module}):
        yield mock_anthropic_module


def test_generate_mock_returns_mock_response():
    """Verify that the mock model returns the expected mock response."""
    prompt = "Hello, world!"
    model = "mock"
    response = provider.generate(prompt, model)
    assert "[MOCK RESPONSE]" in response
    assert prompt[:80] in response


def test_generate_unknown_model_raises_value_error():
    """Verify that an unknown model name raises a ValueError."""
    with pytest.raises(ValueError, match="Unknown model: 'invalid-model'"):
        provider.generate("test prompt", "invalid-model")


@patch.dict(
    os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project", "VERTEXAI_LOCATION": "us-central1"}
)
def test_generate_gemini_model_succeeds(mock_vertexai):
    """Test that the Gemini provider can be called successfully."""
    # We need to manually update the global var because patch.dict happens after import
    provider._VERTEXAI_PROJECT = "test-project"

    response = provider.generate("test prompt", "gemini-1.5-pro")

    assert response == "Gemini response"
    mock_vertexai.init.assert_called_with(project="test-project", location="us-central1")
    # Access the mock through the fixture which is the module mock
    mock_vertexai.generative_models.GenerativeModel.assert_called()


@patch.dict(os.environ, {}, clear=True)
def test_generate_gemini_missing_project_id_raises_runtime_error(mock_vertexai):
    """Verify that a missing Google Cloud project ID raises a RuntimeError for Gemini."""
    # Force global var to be empty
    provider._VERTEXAI_PROJECT = ""

    with pytest.raises(RuntimeError, match="GOOGLE_CLOUD_PROJECT environment variable is not set"):
        provider.generate("test prompt", "gemini-pro")


@patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
def test_generate_claude_model_succeeds(mock_anthropic):
    """Test that the Claude provider can be called successfully."""
    response = provider.generate("test prompt", "claude-3-opus-20240229")
    assert response == "Claude response"
    mock_anthropic.Anthropic.assert_called_with(api_key="test-key")


@patch.dict(os.environ, {}, clear=True)
def test_generate_claude_missing_api_key_raises_runtime_error(mock_anthropic):
    """Verify that a missing Anthropic API key raises a RuntimeError for Claude."""
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY environment variable is not set"):
        provider.generate("test prompt", "claude-3-opus-20240229")


def test_generate_gemini_import_error():
    """Test that an ImportError is handled correctly for Gemini."""
    provider._VERTEXAI_PROJECT = "test-project"

    # We simulate ImportError by setting the module to None or raising it on access
    # Setting to None works well for 'import X' failure simulation in some contexts,
    # but since we are inside a function, let's mock the init to raise.

    mock_vertex = MagicMock()
    mock_vertex.init.side_effect = ImportError("package not found")

    with patch.dict(sys.modules, {"vertexai": mock_vertex}):
        with pytest.raises(RuntimeError, match=r"Gemini \(Vertex AI\) call failed"):
            provider.generate("test prompt", "gemini-1.5-pro")


def test_generate_claude_import_error():
    """Test that an ImportError is handled correctly for Claude."""
    mock_anthropic = MagicMock()
    mock_anthropic.Anthropic.side_effect = ImportError("package not found")

    # We must set the API key, otherwise the code fails before importing
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            with pytest.raises(RuntimeError, match="Claude call failed"):
                provider.generate("test prompt", "claude-3-opus-20240229")
