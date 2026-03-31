"""Reusable KFP components for BigQuery operations."""

import json
from datetime import datetime, timezone

from google.cloud import bigquery, storage
from kfp import dsl

UTC = timezone.utc


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=[
        "google-cloud-bigquery==3.25.0",
        "google-cloud-storage==2.18.0",
    ],
)
def fetch_logs_to_gcs(
    project_id: str,
    app_id: str,
    lookback_hours: int,
    sample_size: int,
    output_gcs_uri: dsl.Output[dsl.Artifact],
) -> None:
    """Fetch BigQuery logs and write to GCS as JSON.

    Uses GCS artifact output to handle large log sets without KFP parameter limits.
    """


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
          AND CHAR_LENGTH(output) > 10
        ORDER BY RAND()
        LIMIT {sample_size}
    """

    rows = [dict(r) for r in client.query(query).result()]
    print(f"Fetched {len(rows)} log rows for {app_id}")

    # Write to GCS via artifact
    gcs_path = output_gcs_uri.uri
    bucket_name = gcs_path.replace("gs://", "").split("/")[0]
    blob_name = "/".join(gcs_path.replace("gs://", "").split("/")[1:])

    gcs_client = storage.Client(project=project_id)
    bucket = gcs_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(json.dumps(rows), content_type="application/json")
    print(f"Logs written to {gcs_path}")


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=[
        "google-cloud-bigquery==3.25.0",
        "google-cloud-storage==2.18.0",
    ],
)
def write_scores_to_bigquery(
    scored_gcs_uri: dsl.Input[dsl.Artifact],
    project_id: str,
    eval_run_id: str,
    app_id: str,
) -> float:
    """Read scored rows from GCS and write to BigQuery evaluation_results. Returns avg score."""

    from google.cloud import bigquery, storage

    # Read from GCS artifact
    gcs_path = scored_gcs_uri.uri
    bucket_name = gcs_path.replace("gs://", "").split("/")[0]
    blob_name = "/".join(gcs_path.replace("gs://", "").split("/")[1:])

    gcs_client = storage.Client(project=project_id)
    content = gcs_client.bucket(bucket_name).blob(blob_name).download_as_text()
    scored = json.loads(content)

    if not scored:
        print("No scored rows to write.")
        return 0.0

    bq = bigquery.Client(project=project_id)
    table = f"{project_id}.llmops.evaluation_results"
    now = datetime.now(UTC).isoformat()

    rows = [
        {
            "timestamp": now,
            "eval_run_id": eval_run_id,
            "app_id": app_id,
            "request_timestamp": r.get("timestamp", ""),
            "user_input": r.get("user_input", "")[:2000],
            "output": r.get("output", "")[:4000],
            "pipeline_executed": r.get("pipeline_executed", ""),
            "prompt_version": r.get("prompt_version", ""),
            "model": r.get("model", ""),
            "correctness_score": r.get("correctness_score"),
            "relevance_score": r.get("relevance_score"),
            "completeness_score": r.get("completeness_score"),
            "avg_score": r.get("avg_score"),
            "judge_model": r.get("judge_model", ""),
            "judge_explanation": r.get("judge_explanation", "")[:1000],
        }
        for r in scored
    ]

    errors = bq.insert_rows_json(table, rows)
    if errors:
        print(f"BigQuery insert errors: {errors}")

    avg = round(sum(r.get("avg_score", 0) for r in scored) / len(scored), 2)
    print(f"Wrote {len(rows)} eval rows. Average score: {avg}")
    return avg
