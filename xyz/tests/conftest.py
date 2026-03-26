"""Shared pytest fixtures for the LLMOps test suite.

Provides reusable fixtures and mock objects for testing the LLMOps backend.
Follows agent-foundation patterns with pytest-mock and typed fixtures.
"""

from unittest.mock import patch
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

MOCK_CONFIG = {
    "pipeline": "llm",
    "model": "mock",
    "active_model": "mock",
    "active_prompt_version": "v1",
    "prompt_template": "User: {user_input}",
    "system_prompt": "You are a test assistant.",
    "evaluation_threshold": 3.0,
    "description": "Test config",
}

RAG_CONFIG = {
    **MOCK_CONFIG,
    "pipeline": "rag",
    "prompt_template": "Context:\n{context}\n\nUser: {user_input}",
    "top_k": 2,
    "rag_corpus_id": "projects/test/locations/us-central1/ragCorpora/123",
}

AGENT_CONFIG = {
    **MOCK_CONFIG,
    "pipeline": "agent",
    "max_iterations": 2,
    "system_prompt": "You are a test agent.",
}


@pytest.fixture
def mock_config() -> dict:
    """Return a mock LLM app config."""
    return MOCK_CONFIG.copy()


@pytest.fixture
def rag_config() -> dict:
    """Return a mock RAG app config."""
    return RAG_CONFIG.copy()


@pytest.fixture
def agent_config() -> dict:
    """Return a mock agent app config."""
    return AGENT_CONFIG.copy()


@pytest.fixture
def mock_detection_llm() -> dict:
    """Task detection result routing to LLM pipeline."""
    return {"needs_rag": False, "needs_agent": False}


@pytest.fixture
def mock_detection_rag() -> dict:
    """Task detection result routing to RAG pipeline."""
    return {"needs_rag": True, "needs_agent": False}


@pytest.fixture
def mock_detection_agent() -> dict:
    """Task detection result routing to Agent pipeline."""
    return {"needs_rag": False, "needs_agent": True}


def mock_load_config_side_effect(app_id: str):
    if app_id in ["mock_app", "default_llm", "rag_bot", "code_agent"]:
        return MOCK_CONFIG
    raise KeyError(f"App ID '{app_id}' not found.")


@pytest.fixture
def test_client():
    """FastAPI test client with mocked config and logging."""
    with (
        patch("utils.config_loader.load_config", side_effect=mock_load_config_side_effect),
        patch("app.services.logging_service.log_request", return_value=None),
        patch(
            "app.services.task_detector.detect",
            return_value={"needs_rag": False, "needs_agent": False},
        ),
        patch("app.services.llm_provider.generate", return_value="This is a mock response."),
    ):
        from app.main import app

        yield TestClient(app)
