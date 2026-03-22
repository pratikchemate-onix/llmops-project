"""
LLM Provider — unified interface for all model calls.
Uses Vertex AI for Gemini (no API key needed — uses Application Default Credentials).
Uses Anthropic SDK for Claude (needs ANTHROPIC_API_KEY env var).
Uses mock for testing without any credentials.
"""

import logging
import os

logger = logging.getLogger(__name__)

# Vertex AI project and location — set these in your environment
_VERTEXAI_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
_VERTEXAI_LOCATION = os.getenv("VERTEXAI_LOCATION", "us-central1")
_VERTEXAI_INITIALIZED = False


def _init_vertexai() -> None:
    """Initialize Vertex AI once per process. Uses ADC — no API key needed."""
    global _VERTEXAI_INITIALIZED
    if _VERTEXAI_INITIALIZED:
        return
    if not _VERTEXAI_PROJECT:
        raise RuntimeError(
            "GOOGLE_CLOUD_PROJECT environment variable is not set. "
            "Set it to your GCP project ID."
        )
    import vertexai

    vertexai.init(project=_VERTEXAI_PROJECT, location=_VERTEXAI_LOCATION)
    _VERTEXAI_INITIALIZED = True
    logger.info(
        f"Vertex AI initialized: project={_VERTEXAI_PROJECT}, " f"location={_VERTEXAI_LOCATION}"
    )


# Map our simple model names to Vertex AI model IDs (Publisher paths)
_GEMINI_MODEL_MAP = {
    # Main models
    "gemini": "gemini-2.5-flash",
    "gemini-2.5-flash": "gemini-2.5-flash",
    "gemini-2.5-flash-preview": "publishers/google/models/gemini-2.5-flash-lite-preview-09-2025",
    "gemini-2.5-flash-lite": "publishers/google/models/gemini-2.5-flash-lite",
    "gemini-3.1-flash-lite": "gemini-3.1-flash-lite-preview",
    # Fallbacks/Aliases for compatibility
    "gemini-flash": "gemini-2.5-flash",
    "gemini-pro": "gemini-2.0-flash-001",
}


def generate(prompt: str, model: str) -> str:
    """Call the appropriate LLM provider based on model name.

    Args:
        prompt: The full formatted prompt string.
        model: One of 'mock', 'gemini', 'gemini-pro', 'gemini-flash', 'claude'.

    Returns:
        The model's text response as a string.

    Raises:
        ValueError: If model name is not recognized.
        RuntimeError: If the API call fails or credentials are missing.
    """
    if model == "mock":
        return f"[MOCK RESPONSE] Received: {prompt[:100]}..."

    if model.lower().startswith("gemini"):
        return _call_gemini_vertex(prompt, model)

    if model.lower().startswith("claude"):
        return _call_claude(prompt)

    raise ValueError(
        f"Unknown model: '{model}'. "
        f"Valid values: mock, gemini, gemini-pro, gemini-flash, claude"
    )


def _call_gemini_vertex(prompt: str, model_alias: str) -> str:
    """Call Gemini via Vertex AI using Application Default Credentials."""
    try:
        _init_vertexai()
        from vertexai.generative_models import GenerationConfig, GenerativeModel

        # Default to the main flash model if alias not found
        model_id = _GEMINI_MODEL_MAP.get(model_alias, "gemini-2.5-flash")

        # Check cache first
        global _GEMINI_MODELS
        if "_GEMINI_MODELS" not in globals():
            _GEMINI_MODELS = {}

        if model_id not in _GEMINI_MODELS:
            logger.info(f"Initializing Vertex AI Gemini model: {model_id}")
            _GEMINI_MODELS[model_id] = GenerativeModel(model_id)

        logger.info(f"Calling Vertex AI Gemini: {model_id}")
        model_obj = _GEMINI_MODELS[model_id]

        response = model_obj.generate_content(
            prompt,
            generation_config=GenerationConfig(
                temperature=0.2,
                max_output_tokens=2048,
            ),
        )
        return response.text

    except Exception as e:
        logger.error(f"Vertex AI Gemini call failed: {e}")
        raise RuntimeError(f"Gemini (Vertex AI) call failed: {str(e)}") from e


def _call_claude(prompt: str) -> str:
    """Call Claude via Anthropic SDK."""
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        message = client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    except KeyError as e:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set.") from e
    except Exception as e:
        logger.error(f"Claude API call failed: {e}")
        raise RuntimeError(f"Claude call failed: {str(e)}") from e
