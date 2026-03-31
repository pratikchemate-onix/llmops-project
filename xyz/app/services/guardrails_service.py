import logging
import os
import re

from app.services.llm_provider import generate
from app.services.prompt_manager import prompt_manager

logger = logging.getLogger(__name__)

# Basic PII regex patterns
PII_PATTERNS = {
    "email": r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "credit_card": r"\b(?:\d[ -]*?){13,16}\b",
}

# List of forbidden words/phrases for output filtering (simple placeholder)
TOXIC_CONTENT_KEYWORDS = ["[placeholder-toxic-word]", "[malicious-intent-detected]"]

class GuardrailsService:
    """Provides input validation and output filtering for LLM interactions."""

    def __init__(self, use_llm_guard: bool = True):
        self.use_llm_guard = use_llm_guard
        self.max_input_length = 4000

    def validate_input(self, user_input: str, model: str = "gemini-2.5-flash") -> tuple[bool, str]:
        """
        Validates user input for safety and quality.
        Returns (is_safe, error_message).
        """
        # 1. Basic length check
        if len(user_input) > self.max_input_length:
            return False, f"Input too long (max {self.max_input_length} characters)."

        if not user_input.strip():
            return False, "Input cannot be empty."

        # 2. Prompt injection check (using LLM-as-a-judge if enabled)
        if self.use_llm_guard:
            try:
                # We use the prompt manager for the injection detection prompt
                prompt_template = prompt_manager.get_prompt("injection_detection")
                check_prompt = prompt_template.format(user_input=user_input)

                # Use a fast model for the check
                # Default to gemini-2.5-flash if GCP project is available, otherwise the requested model
                check_model = "gemini-2.5-flash" if os.getenv("GOOGLE_CLOUD_PROJECT") else model

                response = generate(check_prompt, model=check_model).strip().upper()

                if "UNSAFE" in response or "INJECTION" in response:
                    logger.warning(f"Guardrails: Prompt injection attempt detected: {user_input[:100]}...")
                    return False, "Unsafe input detected. Please rephrase your request."

            except Exception as e:
                logger.error(f"Guardrails: Input validation LLM check failed: {e}")
                # Fallback to allow if LLM check fails to avoid blocking the service
                pass

        return True, ""

    def filter_output(self, output: str) -> str:
        """
        Filters model output for PII or unsafe content.
        """
        filtered = output

        # 1. Basic PII masking
        for pii_type, pattern in PII_PATTERNS.items():
            matches = re.findall(pattern, filtered)
            if matches:
                logger.info(f"Guardrails: Masking {len(matches)} occurrences of {pii_type} in output.")
                filtered = re.sub(pattern, f"[REDACTED {pii_type.upper()}]", filtered)

        # 2. Simple toxic keyword filtering
        for word in TOXIC_CONTENT_KEYWORDS:
            if word in filtered.lower():
                logger.warning(f"Guardrails: Detected unsafe keyword '{word}' in output.")
                filtered = filtered.replace(word, "[REDACTED UNSAFE CONTENT]")

        return filtered

# Global instance
guardrails = GuardrailsService()
