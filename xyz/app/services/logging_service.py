"""
Structured logging to BigQuery. Falls back to stdout if BigQuery is unavailable.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

UTC = timezone.utc

logger = logging.getLogger(__name__)

_BQ_CLIENT = None

def _get_bq_client() -> tuple[Any, str]:
    global _BQ_CLIENT
    project = os.getenv("BIGQUERY_PROJECT")
    if _BQ_CLIENT is None and project:
        try:
            from google.cloud import bigquery  # type: ignore
            _BQ_CLIENT = bigquery.Client(project=project)
        except Exception as e:
            logger.warning(f"BigQuery init failed: {e}. Using stdout logging.")

    return _BQ_CLIENT, project or ""


def log_request(
    request_id: str,
    app_id: str,
    user_input: str,
    output: str,
    pipeline_executed: str,
    latency_ms: float,
    task_detection: dict,
    config: dict,
    session_id: str | None = None,
    retrieved_chunks: int | None = None,
    guardrail_pass: bool | None = None,
    usage: dict | None = None,
) -> None:
    """Log a completed invoke request to BigQuery."""
    usage = usage or {}
    now = datetime.now(UTC)
    row = {
        "request_id": request_id,
        "timestamp": now.isoformat(),
        "app_id": app_id,
        "session_id": session_id,
        "user_input": user_input[:2000],
        "output": output[:4000],
        "pipeline_executed": pipeline_executed,
        "model": str(config.get("active_model", config.get("model", "unknown"))),
        "prompt_version": str(config.get("active_prompt_version", "unknown")),
        "latency_ms": round(latency_ms, 2),
        "input_length": len(user_input),
        "output_length": len(output),
        "needs_rag": bool(task_detection.get("needs_rag", False)),
        "needs_agent": bool(task_detection.get("needs_agent", False)),
        "retrieved_chunks": retrieved_chunks,
        "guardrail_pass": guardrail_pass,
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_cost": float(usage.get("total_cost", 0.0)),
    }

    client, project = _get_bq_client()
    if client and project:
        try:
            table = f"{project}.llmops.requests"
            errors = client.insert_rows_json(table, [row])
            if errors:
                logger.error(f"BigQuery insert errors: {errors}")
        except Exception as e:
            logger.error(f"BigQuery insert failed: {e}")
            _log_to_stdout("INVOKE", row)
    else:
        _log_to_stdout("INVOKE", row)

def log_evaluation(request_id: str, criteria: str, score: float, reasoning: str) -> None:
    """Log an automated evaluation of a request."""
    now = datetime.now(UTC)
    row = {
        "request_id": request_id,
        "timestamp": now.isoformat(),
        "criteria": criteria,
        "score": score,
        "reasoning": reasoning[:2000],
    }

    client, project = _get_bq_client()
    if client and project:
        try:
            table = f"{project}.llmops.evaluations"
            errors = client.insert_rows_json(table, [row])
            if errors:
                logger.error(f"BQ evaluation insert errors: {errors}")
        except Exception as e:
            logger.error(f"BQ evaluation insert failed: {e}")
            _log_to_stdout("EVAL", row)
    else:
        _log_to_stdout("EVAL", row)

def log_feedback(request_id: str, score: int, comment: str | None) -> None:
    """Log user feedback for a request."""
    now = datetime.now(UTC)
    row = {
        "request_id": request_id,
        "timestamp": now.isoformat(),
        "score": score,
        "comment": (comment[:1000] if comment else None),
    }

    client, project = _get_bq_client()
    if client and project:
        try:
            table = f"{project}.llmops.feedback"
            errors = client.insert_rows_json(table, [row])
            if errors:
                logger.error(f"BQ feedback insert errors: {errors}")
        except Exception as e:
            logger.error(f"BQ feedback insert failed: {e}")
            _log_to_stdout("FEEDBACK", row)
    else:
        _log_to_stdout("FEEDBACK", row)

def _log_to_stdout(tag: str, row: dict) -> None:
    logger.info(f"{tag}_LOG: {json.dumps(row)}")
