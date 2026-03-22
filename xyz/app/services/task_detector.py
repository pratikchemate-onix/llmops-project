import json
import logging
import os

logger = logging.getLogger(__name__)

DETECTION_PROMPT = """Analyze this user request and classify it. Return ONLY valid JSON, nothing else.

User request: "{user_input}"

Rules:
- needs_rag: true if the user is asking about specific documents, files, policies, or internal data
- needs_agent: true if the user needs multi-step reasoning, code execution, or tool use

Return exactly: {{"needs_rag": true/false, "needs_agent": true/false}}"""

_CLASSIFIER_MODEL = None


def detect(user_input: str, model: str) -> dict:
    """Classify user intent to determine pipeline routing.

    Returns:
        dict with keys needs_rag (bool) and needs_agent (bool).
    """
    global _CLASSIFIER_MODEL

    if model == "mock":
        return {"needs_rag": False, "needs_agent": False}

    try:
        if _CLASSIFIER_MODEL is None:
            import vertexai
            from vertexai.generative_models import GenerativeModel

            project = os.getenv("GOOGLE_CLOUD_PROJECT", "")
            location = os.getenv("VERTEXAI_LOCATION", "us-central1")

            # Initialize only if project is set to avoid errors in local tests without env vars
            if project:
                vertexai.init(project=project, location=location)

            # Always use Flash for classification — fast and cheap
            _CLASSIFIER_MODEL = GenerativeModel("gemini-2.5-flash")

        classifier = _CLASSIFIER_MODEL
        prompt = DETECTION_PROMPT.format(user_input=user_input)
        response = classifier.generate_content(prompt)

        raw = response.text.strip()

        # Handle simple string keywords first
        if "NEEDS_RAG" in raw:
            return {"needs_rag": True, "needs_agent": False}
        if "NEEDS_AGENT" in raw:
            return {"needs_rag": False, "needs_agent": True}

        # Cleanup potential markdown formatting
        if raw.startswith("```json"):
            raw = raw[7:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        result = json.loads(raw)
        return {
            "needs_rag": bool(result.get("needs_rag", False)),
            "needs_agent": bool(result.get("needs_agent", False)),
        }
    except Exception as e:
        logger.warning(f"Task detection failed, using defaults: {e}")
        return {"needs_rag": False, "needs_agent": False}
