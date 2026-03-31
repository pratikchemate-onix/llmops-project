"""
KFP Pipeline: Nightly LLM-as-Judge Evaluation
Triggered by: Cloud Scheduler (2am daily)
What it does:
  1. Fetches last 24h of requests from BigQuery
  2. Scores each response using Gemini as the judge model (LLM-as-judge)
  3. Writes scores to BigQuery evaluation_results table
  4. If average score < threshold, promotes best candidate prompt in Firestore

Deploy with:
  python pipelines/evaluation_pipeline.py --project YOUR_PROJECT --submit
"""

import os
from datetime import timezone
UTC = timezone.utc

import google.cloud.aiplatform as aip
from kfp import dsl

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.getenv("PIPELINE_LOCATION", "us-central1")
PIPELINE_ROOT = os.getenv("PIPELINE_ROOT_GCS", "")

JUDGE_PROMPT = """You are an expert AI quality evaluator.
Evaluate the following AI assistant response on THREE criteria.
Return ONLY valid JSON, nothing else.

User Question: {user_input}
AI Response: {output}
Pipeline Used: {pipeline}

Score each criterion from 1 to 5:
- correctness: Is the response factually accurate and complete?
- relevance: Does it directly address what the user asked?
- completeness: Does it fully answer the question?

Return exactly:
{{"correctness": 1-5, "relevance": 1-5, "completeness": 1-5, "explanation": "brief reason"}}"""


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["google-cloud-bigquery", "pandas"],
)
def fetch_recent_logs(
    project_id: str,
    app_id: str,
    lookback_hours: int,
    sample_size: int,
) -> str:
    """Fetch recent log rows from BigQuery for the given app_id."""
    import json

    from google.cloud import bigquery

    client = bigquery.Client(project=project_id)
    query = f"""
        SELECT
            CAST(timestamp AS STRING) as timestamp,
            app_id, user_input, output,
            pipeline_executed, prompt_version, model, latency_ms
        FROM `{project_id}.llmops.requests`
        WHERE app_id = '{app_id}'
          AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {lookback_hours} HOUR)
          AND output IS NOT NULL
          AND LENGTH(output) > 10
        ORDER BY RAND()
        LIMIT {sample_size}
    """
    rows = [dict(r) for r in client.query(query).result()]
    return json.dumps(rows)


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["google-generativeai"],
)
def score_with_llm_judge(
    logs_json: str,
    judge_model: str,
    project_id: str,
) -> str:
    """Use LLM-as-judge to score each response. Returns JSON list of scored rows."""
    import json
    import os
    import time

    import google.generativeai as genai

    logs = json.loads(logs_json)
    if not logs:
        return json.dumps([])

    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    model = genai.GenerativeModel(judge_model)

    judge_prompt_template = """You are an expert AI quality evaluator.
Evaluate this AI assistant response. Return ONLY valid JSON.

User Question: {user_input}
AI Response: {output}

Score each from 1-5:
- correctness: Is the response factually accurate?
- relevance: Does it address what was asked?
- completeness: Is it fully answered?

Return exactly: {{"correctness": N, "relevance": N, "completeness": N, "explanation": "reason"}}"""

    scored = []
    for row in logs:
        try:
            prompt = judge_prompt_template.format(
                user_input=row.get("user_input", ""),
                output=row.get("output", ""),
            )
            resp = model.generate_content(prompt)
            raw = resp.text.strip().strip("```json").strip("```").strip()
            scores = json.loads(raw)

            avg = round(
                (
                    scores.get("correctness", 3)
                    + scores.get("relevance", 3)
                    + scores.get("completeness", 3)
                )
                / 3,
                2,
            )

            scored.append(
                {
                    **row,
                    "correctness_score": scores.get("correctness", 3),
                    "relevance_score": scores.get("relevance", 3),
                    "completeness_score": scores.get("completeness", 3),
                    "avg_score": avg,
                    "judge_model": judge_model,
                    "judge_explanation": scores.get("explanation", ""),
                }
            )
            time.sleep(0.5)  # avoid rate limiting
        except Exception as e:
            print(f"Scoring failed for row: {e}")
            continue

    return json.dumps(scored)


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["google-cloud-bigquery"],
)
def write_scores_to_bigquery(
    scored_json: str,
    project_id: str,
    eval_run_id: str,
) -> float:
    """Write evaluation scores to BigQuery. Returns average score."""
    import json
    from datetime import datetime

    from google.cloud import bigquery

    scored = json.loads(scored_json)
    if not scored:
        print("No scored rows to write.")
        return 0.0

    client = bigquery.Client(project=project_id)
    table = f"{project_id}.llmops.evaluation_results"
    now = datetime.now(UTC).isoformat()

    rows = []
    for row in scored:
        rows.append(
            {
                "timestamp": now,
                "eval_run_id": eval_run_id,
                "app_id": row.get("app_id", ""),
                "request_timestamp": row.get("timestamp", ""),
                "user_input": row.get("user_input", "")[:2000],
                "output": row.get("output", "")[:4000],
                "pipeline_executed": row.get("pipeline_executed", ""),
                "prompt_version": row.get("prompt_version", ""),
                "model": row.get("model", ""),
                "correctness_score": row.get("correctness_score"),
                "relevance_score": row.get("relevance_score"),
                "completeness_score": row.get("completeness_score"),
                "avg_score": row.get("avg_score"),
                "judge_model": row.get("judge_model", ""),
                "judge_explanation": row.get("judge_explanation", "")[:1000],
            }
        )

    errors = client.insert_rows_json(table, rows)
    if errors:
        print(f"BigQuery errors: {errors}")

    avg = round(sum(r.get("avg_score", 0) for r in scored) / len(scored), 2)
    print(f"Wrote {len(rows)} rows. Average score: {avg}")
    return avg


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["google-cloud-firestore"],
)
def update_config_if_needed(
    app_id: str,
    avg_score: float,
    project_id: str,
) -> str:
    """
    If avg_score < evaluation_threshold:
      Find the highest-scoring candidate prompt in Firestore.
      Promote it to active if its stored score > current avg.
    Returns action taken.
    """
    from datetime import datetime

    from google.cloud import firestore

    db = firestore.Client(project=project_id)
    config_ref = db.collection("configs").document(app_id)
    config = config_ref.get().to_dict()

    threshold = config.get("evaluation_threshold", 4.0)
    current_version = config.get("active_prompt_version", "v1")

    if avg_score >= threshold:
        return f"Score {avg_score} meets threshold {threshold}. No change."

    print(
        f"Score {avg_score} below threshold {threshold}. Looking for better prompt..."
    )

    # Find best candidate prompt (status=candidate, score > avg_score)
    prompts = (
        config_ref.collection("prompts").where("status", "==", "candidate").stream()
    )
    best_version = None
    best_score = avg_score

    for p in prompts:
        pd = p.to_dict()
        if pd.get("score", 0) > best_score:
            best_score = pd.get("score", 0)
            best_version = p.id

    if best_version:
        config_ref.update(
            {
                "active_prompt_version": best_version,
                "updated_at": datetime.now(UTC),
            }
        )
        # Mark old as retired, new as active
        config_ref.collection("prompts").document(current_version).update(
            {"status": "retired"}
        )
        config_ref.collection("prompts").document(best_version).update(
            {"status": "active"}
        )
        return f"Promoted prompt {best_version} (score {best_score}) over {current_version} (score {avg_score})"

    return (
        f"No better candidate found. Current score: {avg_score}. Manual review needed."
    )


@dsl.pipeline(
    name="llmops-evaluation",
    description="Nightly LLM-as-judge evaluation with auto config update",
)
def evaluation_pipeline(
    app_id: str = "default_llm",
    project_id: str = PROJECT_ID,
    judge_model: str = "gemini-2.0-pro",
    lookback_hours: int = 24,
    sample_size: int = 50,
    eval_run_id: str = "eval_run",
):
    fetch_task = fetch_recent_logs(
        project_id=project_id,
        app_id=app_id,
        lookback_hours=lookback_hours,
        sample_size=sample_size,
    )

    score_task = score_with_llm_judge(
        logs_json=fetch_task.output,
        judge_model=judge_model,
        project_id=project_id,
    ).after(fetch_task)

    write_task = write_scores_to_bigquery(
        scored_json=score_task.output,
        project_id=project_id,
        eval_run_id=eval_run_id,
    ).after(score_task)

    update_config_if_needed(
        app_id=app_id,
        avg_score=write_task.output,
        project_id=project_id,
    ).after(write_task)


if __name__ == "__main__":
    import argparse

    from kfp import compiler

    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--app_id", default="default_llm")
    parser.add_argument("--submit", action="store_true")
    args = parser.parse_args()

    if args.submit:
        aip.init(project=args.project, location=LOCATION)
        from kfp import compiler as kfp_compiler

        compiled = "/tmp/evaluation_pipeline.json"
        kfp_compiler.Compiler().compile(evaluation_pipeline, compiled)
        job = aip.PipelineJob(
            display_name="eval-run",
            template_path=compiled,
            pipeline_root=PIPELINE_ROOT,
            parameter_values={
                "app_id": args.app_id,
                "project_id": args.project,
            },
            enable_caching=False,
        )
        job.submit()
        print("Evaluation pipeline submitted.")
    else:
        compiler = __import__("kfp", fromlist=["compiler"]).compiler
        compiler.Compiler().compile(evaluation_pipeline, "evaluation_pipeline.json")
        print("Compiled to evaluation_pipeline.json")
