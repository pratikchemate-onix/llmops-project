import logging
import asyncio
from app.services.llm_provider import generate
from app.services.logging_service import log_evaluation

logger = logging.getLogger(__name__)

EVAL_PROMPT = """You are an impartial AI judge. Evaluate the following AI assistant response.
Rate the response on a scale of 1 to 5 (1 = terrible/hallucinated, 5 = excellent/accurate).

User Input: {user_input}
AI Response: {output}

Return your evaluation exactly in this format:
SCORE: [1-5]
REASONING: [Brief explanation]
"""

async def evaluate_response_async(request_id: str, user_input: str, output: str, model_name: str = "gemini-2.5-flash") -> None:
    """Runs a background evaluation of an LLM response."""
    try:
        # Yield to event loop
        await asyncio.sleep(0.1)
        
        prompt = EVAL_PROMPT.format(user_input=user_input, output=output)
        
        logger.info(f"Starting background evaluation for request {request_id}")
        # Call model to get score
        eval_result = generate(prompt, model=model_name)
        
        score = 0.0
        reasoning = "Parsing failed"
        
        for line in eval_result.split("
"):
            line = line.strip()
            if line.startswith("SCORE:"):
                try:
                    score = float(line.replace("SCORE:", "").strip())
                except ValueError:
                    pass
            elif line.startswith("REASONING:"):
                reasoning = line.replace("REASONING:", "").strip()
                
        if score > 0:
            logger.info(f"Evaluation complete for {request_id}. Score: {score}")
            log_evaluation(request_id=request_id, criteria="general_quality", score=score, reasoning=reasoning)
        else:
            logger.warning(f"Evaluation failed to parse output for {request_id}: {eval_result}")
            
    except Exception as e:
        logger.error(f"Background evaluation failed for {request_id}: {e}")
