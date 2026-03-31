import asyncio
import contextlib
import logging

from app.services.llm_provider import generate
from app.services.logging_service import log_evaluation
from app.services.prompt_manager import prompt_manager

logger = logging.getLogger(__name__)

async def evaluate_response_async(request_id: str, user_input: str, output: str, model_name: str = "gemini-2.5-flash") -> None:
    """Runs a background evaluation of an LLM response."""
    try:
        # Yield to event loop
        await asyncio.sleep(0.1)

        prompt_template = prompt_manager.get_prompt("evaluation")
        prompt = prompt_template.format(user_input=user_input, output=output)

        logger.info(f"Starting background evaluation for request {request_id}")
        # Call model to get score
        eval_result = generate(prompt, model=model_name)

        score = 0.0
        reasoning = "Parsing failed"

        for line in eval_result.split("\n"):
            line = line.strip()
            if line.startswith("SCORE:"):
                with contextlib.suppress(ValueError):
                    score = float(line.replace("SCORE:", "").strip())
            elif line.startswith("REASONING:"):
                reasoning = line.replace("REASONING:", "").strip()

        if score > 0:
            logger.info(f"Evaluation complete for {request_id}. Score: {score}")
            log_evaluation(request_id=request_id, criteria="general_quality", score=score, reasoning=reasoning)
        else:
            logger.warning(f"Evaluation failed to parse output for {request_id}: {eval_result}")

    except Exception as e:
        logger.error(f"Background evaluation failed for {request_id}: {e}")
