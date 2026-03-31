import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.orchestrator.router import get_pipeline
from app.services.evaluation_service import evaluate_response_async
from app.services.guardrails_service import guardrails
from app.services.llm_provider import usage_context
from app.services.logging_service import log_feedback, log_request
from app.services.task_detector import detect
from utils.config_loader import load_config

logger = logging.getLogger(__name__)

router = APIRouter()


class InvokeRequest(BaseModel):
    app_id: str
    user_input: str
    model: str | None = None


class TaskDetectionResult(BaseModel):
    needs_rag: bool
    needs_agent: bool


class UsageMetrics(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_cost: float


class InvokeResponse(BaseModel):
    request_id: str
    app_id: str
    user_input: str
    config: dict[str, Any]
    task_detection: TaskDetectionResult
    pipeline_executed: str
    output: str
    latency_ms: float
    usage: UsageMetrics


class FeedbackRequest(BaseModel):
    request_id: str
    score: int
    comment: str | None = None


@router.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    """Endpoint for users to submit thumbs up/down and comments for a specific AI response."""
    try:
        log_feedback(request.request_id, request.score, request.comment)
        return {"status": "success", "message": "Feedback logged."}
    except Exception as e:
        logger.error(f"Failed to log feedback: {e}")
        raise HTTPException(status_code=500, detail="Failed to log feedback") from e


@router.post("/invoke", response_model=InvokeResponse)
async def invoke_pipeline(request: InvokeRequest, background_tasks: BackgroundTasks) -> InvokeResponse:
    start_time = time.time()
    request_id = str(uuid.uuid4())
    logger.info(f"Received invoke request {request_id} for app_id={request.app_id}")

    # Reset usage context for this new request lifecycle
    usage_context.set({"prompt_tokens": 0, "completion_tokens": 0, "total_cost": 0.0})

    try:
        # 0. Guardrails: Input validation
        is_safe, error_msg = guardrails.validate_input(request.user_input, model=request.model or "gemini-2.5-flash")
        if not is_safe:
            logger.warning(f"Guardrails: blocked input for {request_id}: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

        # 1. Load config
        try:
            config = load_config(request.app_id)
            if request.model:
                config["model"] = request.model
                config["active_model"] = request.model
            logger.info(
                f"Config loaded: pipeline={config.get('pipeline')}, model={config.get('active_model')}"
            )
        except KeyError as e:
            logger.error(f"App ID not found: {request.app_id}")
            raise HTTPException(
                status_code=404, detail=f"App ID '{request.app_id}' not found."
            ) from e
        except FileNotFoundError as e:
            logger.critical("Configuration file missing.")
            raise HTTPException(
                status_code=500, detail="Configuration file missing."
            ) from e

        # 2. Task Detection
        try:
            # We pass the model from config to task detector
            model_name = config.get("model", "mock")
            detection_data = detect(request.user_input, model_name)
            logger.info(f"Task detection result: {detection_data}")
        except Exception as e:
            logger.warning(f"Task detection failed: {e}")
            # Fallback is handled inside detect(), but extra safety here
            detection_data = {"needs_rag": False, "needs_agent": False}

        # 3. Route to Pipeline
        try:
            pipeline = get_pipeline(config, detection_data)
            logger.info(f"Routing to pipeline: {type(pipeline).__name__}")
        except Exception as e:
            logger.error(f"Orchestration failed: {e}")
            raise HTTPException(
                status_code=500, detail=f"Orchestration failed: {str(e)}"
            ) from e

        # 4. Execute Pipeline
        retrieved_chunks = None
        try:
            logger.info(f"Executing pipeline with input: {request.user_input[:50]}...")
            result = pipeline.execute(request.user_input)
            # RAGPipeline returns (text, num_chunks), others return str
            if isinstance(result, tuple):
                output_text, retrieved_chunks = result
                logger.info(f"Pipeline returned tuple. Chunks: {retrieved_chunks}")
            else:
                output_text = result
                logger.info("Pipeline returned string result.")

            # 4.1 Guardrails: Filter output
            output_text = guardrails.filter_output(output_text)
        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}")
            raise HTTPException(
                status_code=500, detail=f"Pipeline execution failed: {str(e)}"
            ) from e

        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000

        # Get tracked usage
        current_usage = usage_context.get()

        # 5. Logging
        pipeline_name = type(pipeline).__name__.replace("Pipeline", "").lower()
        try:
            log_request(
                request_id=request_id,
                app_id=request.app_id,
                user_input=request.user_input,
                output=output_text,
                pipeline_executed=pipeline_name,
                latency_ms=latency_ms,
                task_detection=detection_data,
                config=config,
                retrieved_chunks=retrieved_chunks,
                usage=current_usage,
            )
            logger.info(f"Request logged. Latency: {latency_ms:.2f}ms")
        except Exception as e:
            # Don't fail the request if logging fails, but log the error
            logger.error(f"Logging service failed: {e}")

        # 6. Background Evaluation
        # Send to eval asynchronously so it doesn't block the user's response
        eval_model = config.get("active_model", "gemini-2.5-flash")
        background_tasks.add_task(
            evaluate_response_async,
            request_id=request_id,
            user_input=request.user_input,
            output=output_text,
            model_name=eval_model
        )

        return InvokeResponse(
            request_id=request_id,
            app_id=request.app_id,
            user_input=request.user_input,
            config=config,
            task_detection=TaskDetectionResult(**detection_data),
            pipeline_executed=pipeline_name,
            output=output_text,
            latency_ms=latency_ms,
            usage=UsageMetrics(**current_usage),
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception("Unexpected error in invoke handler")
        raise HTTPException(
            status_code=500, detail=f"Internal Server Error: {str(e)}"
        ) from e
