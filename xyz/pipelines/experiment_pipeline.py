"""
KFP Pipeline: Model Experiment (A vs B comparison)
Triggered by: Manual or weekly Cloud Scheduler
What it does:
  1. Loads test questions from GCS
  2. Runs both model_a and model_b on each question
  3. Scores both using LLM-as-judge
  4. Writes comparison to BigQuery
  5. Promotes winner to Firestore config if it wins by margin

Usage:
  python pipelines/experiment_pipeline.py --project P --app_id rag_bot \
    --model_a gemini --model_b claude --test_file gs://bucket/test_set.json --submit
"""

import os
from datetime import timezone
UTC = timezone.utc

from kfp import dsl

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.getenv("PIPELINE_LOCATION", "us-central1")
PIPELINE_ROOT = os.getenv("PIPELINE_ROOT_GCS", "")


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["google-cloud-storage"],
)
def load_test_set(gcs_test_file: str, project_id: str) -> str:
    """Load test questions from a GCS JSON file.

    Expected format: [{"question": "...", "expected": "..."}, ...]"""
    from google.cloud import storage

    # Parse gs:// URI
    path = gcs_test_file.replace("gs://", "")
    bucket_name, blob_name = path.split("/", 1)

    client = storage.Client(project=project_id)
    blob = client.bucket(bucket_name).blob(blob_name)
    return blob.download_as_text()


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["google-generativeai", "anthropic", "requests"],
)
def run_model_on_test_set(
    test_set_json: str,
    model_name: str,
    app_id: str,
    invoke_url: str,
) -> str:
    """Run all test questions through the serving API using a specific model override.
    Returns JSON list of {question, response} dicts.
    """
    import json

    import requests

    test_set = json.loads(test_set_json)
    results = []

    for item in test_set[:30]:  # cap at 30 questions per experiment
        try:
            resp = requests.post(
                f"{invoke_url}/invoke",
                json={"app_id": app_id, "user_input": item["question"]},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            results.append(
                {
                    "question": item["question"],
                    "expected": item.get("expected", ""),
                    "model": model_name,
                    "response": data.get("output", ""),
                    "latency_ms": data.get("latency_ms", 0),
                }
            )
        except Exception as e:
            results.append(
                {
                    "question": item["question"],
                    "model": model_name,
                    "response": f"ERROR: {str(e)}",
                    "latency_ms": 0,
                }
            )

    return json.dumps(results)


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["google-generativeai"],
)
def compare_and_score(
    results_a_json: str,
    results_b_json: str,
    model_a_name: str,
    model_b_name: str,
    project_id: str,
) -> str:
    """Score both model results using LLM-as-judge. Returns comparison JSON."""
    import json
    import os
    import time

    import google.generativeai as genai

    results_a = json.loads(results_a_json)
    results_b = json.loads(results_b_json)

    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    judge = genai.GenerativeModel("gemini-2.0-pro")

    scores_a, scores_b = [], []

    for ra, rb in zip(results_a, results_b, strict=False):
        try:
            prompt = f"""Compare two AI responses to the same question. Score each from 1-5.
Return ONLY JSON: {{"score_a": N, "score_b": N, "winner": "a" or "b" or "tie", "reason": "..."}}

Question: {ra["question"]}
Response A ({model_a_name}): {ra["response"]}
Response B ({model_b_name}): {rb["response"]}"""

            resp = judge.generate_content(prompt)
            raw = resp.text.strip().strip("```json").strip("```").strip()
            scored = json.loads(raw)
            scores_a.append(scored.get("score_a", 3))
            scores_b.append(scored.get("score_b", 3))
            time.sleep(0.5)
        except Exception as e:
            print(f"Scoring error: {e}")
            scores_a.append(3)
            scores_b.append(3)

    avg_a = round(sum(scores_a) / len(scores_a), 2) if scores_a else 0
    avg_b = round(sum(scores_b) / len(scores_b), 2) if scores_b else 0
    winner = (
        model_a_name if avg_a > avg_b else (model_b_name if avg_b > avg_a else "tie")
    )

    return json.dumps(
        {
            "model_a": model_a_name,
            "model_b": model_b_name,
            "avg_score_a": avg_a,
            "avg_score_b": avg_b,
            "winner": winner,
            "sample_size": len(scores_a),
        }
    )


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["google-cloud-bigquery", "google-cloud-firestore"],
)
def write_experiment_and_promote(
    comparison_json: str,
    app_id: str,
    experiment_id: str,
    project_id: str,
    promotion_margin: float,
) -> str:
    """Write experiment results to BigQuery and promote winner if margin > threshold."""
    import json
    from datetime import datetime

    from google.cloud import bigquery, firestore

    comparison = json.loads(comparison_json)
    now = datetime.now(UTC)

    # Write to BigQuery
    bq = bigquery.Client(project=project_id)
    row = {
        "timestamp": now.isoformat(),
        "experiment_id": experiment_id,
        "app_id": app_id,
        "model_a": comparison["model_a"],
        "model_b": comparison["model_b"],
        "avg_score_a": comparison["avg_score_a"],
        "avg_score_b": comparison["avg_score_b"],
        "winner": comparison["winner"],
        "promoted": False,
        "sample_size": comparison["sample_size"],
    }
    bq.insert_rows_json(f"{project_id}.llmops.experiments", [row])

    # Promote winner if margin is significant
    winner = comparison["winner"]
    score_a = comparison["avg_score_a"]
    score_b = comparison["avg_score_b"]
    margin = abs(score_a - score_b)

    promoted = False
    if winner != "tie" and margin >= promotion_margin:
        db = firestore.Client(project=project_id)
        db.collection("configs").document(app_id).update(
            {
                "active_model": winner,
                "updated_at": now,
            }
        )
        promoted = True
        print(f"Promoted {winner} for {app_id} (margin: {margin})")

    return f"Experiment complete. Winner: {winner}. Promoted: {promoted}. Margin: {margin:.2f}"


@dsl.pipeline(
    name="llmops-model-experiment",
    description="Compare two models using LLM-as-judge and promote winner",
)
def experiment_pipeline(
    app_id: str = "default_llm",
    model_a_name: str = "gemini",
    model_b_name: str = "claude",
    gcs_test_file: str = "",
    invoke_url: str = "http://localhost:8000",
    experiment_id: str = "exp_001",
    promotion_margin: float = 0.5,
    project_id: str = PROJECT_ID,
):
    load_task = load_test_set(gcs_test_file=gcs_test_file, project_id=project_id)

    run_a = run_model_on_test_set(
        test_set_json=load_task.output,
        model_name=model_a_name,
        app_id=app_id,
        invoke_url=invoke_url,
    ).after(load_task)

    run_b = run_model_on_test_set(
        test_set_json=load_task.output,
        model_name=model_b_name,
        app_id=app_id,
        invoke_url=invoke_url,
    ).after(load_task)

    compare_task = compare_and_score(
        results_a_json=run_a.output,
        results_b_json=run_b.output,
        model_a_name=model_a_name,
        model_b_name=model_b_name,
        project_id=project_id,
    ).after(run_a, run_b)

    write_experiment_and_promote(
        comparison_json=compare_task.output,
        app_id=app_id,
        experiment_id=experiment_id,
        project_id=project_id,
        promotion_margin=promotion_margin,
    ).after(compare_task)
