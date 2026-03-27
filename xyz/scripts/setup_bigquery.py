"""
Run this once to create all BigQuery tables.
Usage: python scripts/setup_bigquery.py --project YOUR_PROJECT_ID
"""

import argparse

from google.cloud import bigquery

SCHEMA_REQUESTS = [
    bigquery.SchemaField("request_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("app_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("session_id", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("user_input", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("output", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("pipeline_executed", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("model", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("prompt_version", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("latency_ms", "FLOAT", mode="REQUIRED"),
    bigquery.SchemaField("input_length", "INTEGER", mode="NULLABLE"),
    bigquery.SchemaField("output_length", "INTEGER", mode="NULLABLE"),
    bigquery.SchemaField("needs_rag", "BOOLEAN", mode="NULLABLE"),
    bigquery.SchemaField("needs_agent", "BOOLEAN", mode="NULLABLE"),
    bigquery.SchemaField("retrieved_chunks", "INTEGER", mode="NULLABLE"),
    bigquery.SchemaField("guardrail_pass", "BOOLEAN", mode="NULLABLE"),
    bigquery.SchemaField("prompt_tokens", "INTEGER", mode="NULLABLE"),
    bigquery.SchemaField("completion_tokens", "INTEGER", mode="NULLABLE"),
    bigquery.SchemaField("total_cost", "FLOAT", mode="NULLABLE"),
]

SCHEMA_FEEDBACK = [
    bigquery.SchemaField("request_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("score", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("comment", "STRING", mode="NULLABLE"),
]

SCHEMA_EVALUATIONS_NEW = [
    bigquery.SchemaField("request_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("criteria", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("score", "FLOAT", mode="REQUIRED"),
    bigquery.SchemaField("reasoning", "STRING", mode="NULLABLE"),
]

SCHEMA_EVALUATION = [
    bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("eval_run_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("app_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("request_timestamp", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("user_input", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("output", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("pipeline_executed", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("prompt_version", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("model", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("correctness_score", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("relevance_score", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("completeness_score", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("avg_score", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("judge_model", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("judge_explanation", "STRING", mode="NULLABLE"),
]

SCHEMA_EXPERIMENTS = [
    bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("experiment_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("app_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("model_a", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("model_b", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("avg_score_a", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("avg_score_b", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("winner", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("promoted", "BOOLEAN", mode="NULLABLE"),
    bigquery.SchemaField("sample_size", "INTEGER", mode="NULLABLE"),
]


def create_tables(project_id: str) -> None:
    client = bigquery.Client(project=project_id)
    dataset_id = f"{project_id}.llmops"

    # Create dataset
    dataset = bigquery.Dataset(dataset_id)
    dataset.location = "asia-south1"
    client.create_dataset(dataset, exists_ok=True)
    print(f"Dataset {dataset_id} ready.")

    tables = {
        "requests": SCHEMA_REQUESTS,
        "feedback": SCHEMA_FEEDBACK,
        "evaluations": SCHEMA_EVALUATIONS_NEW,
        "evaluation_results": SCHEMA_EVALUATION,
        "experiments": SCHEMA_EXPERIMENTS,
    }

    for table_name, schema in tables.items():
        table_ref = f"{dataset_id}.{table_name}"
        table = bigquery.Table(table_ref, schema=schema)
        if table_name == "requests":
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY, field="timestamp"
            )
        client.create_table(table, exists_ok=True)
        print(f"Table {table_ref} ready.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    create_tables(args.project)
    print("BigQuery setup complete.")
