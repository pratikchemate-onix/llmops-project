"""
LLM Provider — unified interface for all model calls.
Uses litellm to support multiple providers (Vertex AI, Anthropic, OpenAI, etc.).
API keys are handled by litellm via standard environment variables
(e.g., ANTHROPIC_API_KEY, OPENAI_API_KEY).
Google Application Default Credentials (ADC) are still used for Vertex AI.
"""

import contextvars
import logging
import os
from datetime import timezone

import litellm

UTC = timezone.utc

logger = logging.getLogger(__name__)

# Context variable to store usage across multiple calls in a single request lifecycle
usage_context: contextvars.ContextVar[dict[str, float] | None] = contextvars.ContextVar(
    "usage_context",
    default=None
)

# Enable opentelemetry tracing
litellm.success_callback = ["opentelemetry"]
litellm.failure_callback = ["opentelemetry"]

# Vertex AI project and location
_VERTEXAI_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
_VERTEXAI_LOCATION = os.getenv("VERTEXAI_LOCATION", "us-central1")

if _VERTEXAI_PROJECT:
    litellm.vertex_project = _VERTEXAI_PROJECT
if _VERTEXAI_LOCATION:
    litellm.vertex_location = _VERTEXAI_LOCATION

# Map our simple model names to litellm standard model identifiers
# For Gemini we use the vertex_ai/ prefix to use ADC
_MODEL_MAP = {
    # Mock
    "mock": "mock",

    # Gemini (via Vertex AI)
    "gemini": "vertex_ai/gemini-2.0-flash-001",
    "gemini-2.0-flash": "vertex_ai/gemini-2.0-flash-001",
    "gemini-2.0-flash-exp": "vertex_ai/gemini-2.0-flash-exp",
    "gemini-2.5-flash": "vertex_ai/gemini-2.0-flash-001",  # Map to 2.0 until 2.5 is available
    "gemini-flash": "vertex_ai/gemini-2.0-flash-001",
    "gemini-pro": "vertex_ai/gemini-1.5-pro",

    # Gemini 3.x models (experimental - may not be available in all projects)
    # Uncomment when these models become publicly available or if your project has access
    # "gemini-3-flash-preview": "vertex_ai/gemini-3-flash-preview",
    # "gemini-3-pro-preview": "vertex_ai/gemini-3-pro-preview",
    # "gemini-3.1-flash-preview": "vertex_ai/gemini-3.1-flash-preview",
    # "gemini-3.1-pro-preview": "vertex_ai/gemini-3.1-pro-preview",

    # Claude
    "claude": "claude-3-opus-20240229",
    "claude-3-opus": "claude-3-opus-20240229",
    "claude-3-sonnet": "claude-3-sonnet-20240229",
    "claude-3-haiku": "claude-3-haiku-20240307",
    "claude-3.5-sonnet": "claude-3-5-sonnet-20241022",

    # OpenAI
    "gpt-4o": "gpt-4o",
    "gpt-4o-mini": "gpt-4o-mini",
    "gpt-3.5-turbo": "gpt-3.5-turbo",

    # xAI (Grok)
    "grok-2-latest": "xai/grok-2-latest",
    "grok-2-1212": "xai/grok-2-1212",

    # Groq
    "llama-3.3-70b-versatile": "groq/llama-3.3-70b-versatile",
}


def generate(prompt: str, model: str) -> str:
    """Call the appropriate LLM provider based on model name using litellm.

    Args:
        prompt: The full formatted prompt string.
        model: The model alias (e.g., 'gemini', 'claude', 'gpt-4o') or a direct litellm identifier.

    Returns:
        The model's text response as a string.

    Raises:
        ValueError: If model name is not recognized and not a valid litellm model.
        RuntimeError: If the API call fails or credentials are missing.
    """
    if model == "mock":
        return f"[MOCK RESPONSE] Received: {prompt[:100]}..."

    # Resolve the model name using our map, fallback to the provided name
    # This allows users to pass native litellm model names directly
    model_id = _MODEL_MAP.get(model.lower(), model)

    if model_id.startswith("vertex_ai/") and not _VERTEXAI_PROJECT:
         raise RuntimeError(
            "GOOGLE_CLOUD_PROJECT environment variable is not set. "
            "Set it to your GCP project ID to use Vertex AI models."
        )

    logger.info(f"LLMProvider: preparing to call litellm model {model_id} (alias: {model})")
    logger.info(f"LLMProvider: calling model {model_id} with prompt length {len(prompt)}")

    try:
        kwargs = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 2048,
        }

        # Gemini 3.x preview models (when available) require vertex_location="global"
        # instead of the default us-central1
        if "gemini-3" in model_id:
            kwargs["vertex_location"] = "global"

        response = litellm.completion(**kwargs)

        # Track usage synchronously to avoid thread contextvar issues
        current_usage = usage_context.get()
        usage = dict(current_usage) if current_usage is not None else {"prompt_tokens": 0, "completion_tokens": 0, "total_cost": 0.0}

        if hasattr(response, "usage") and response.usage:
            usage["prompt_tokens"] += getattr(response.usage, "prompt_tokens", 0)
            usage["completion_tokens"] += getattr(response.usage, "completion_tokens", 0)
        try:
            cost = litellm.completion_cost(response)
            if cost is not None:
                usage["total_cost"] += float(cost)
        except Exception:
            pass
        usage_context.set(usage)

        logger.info("LLMProvider: generation success")
        return response.choices[0].message.content  # type: ignore

    except litellm.AuthenticationError as e:
         logger.error(f"Authentication failed for model {model_id}: {e}")
         raise RuntimeError(f"Authentication failed for {model_id}. Check your API keys or ADC.") from e
    except Exception as e:
        logger.error(f"LLM API call failed for model {model_id}: {e}")
        raise RuntimeError(f"LLM call failed for {model_id}: {str(e)}") from e
