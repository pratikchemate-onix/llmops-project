resource "google_bigquery_dataset" "llmops" {
  dataset_id    = "llmops"
  friendly_name = "LLMOps Pipeline Data"
  description   = "Logs, evaluation results, and experiments"
  location      = var.region

  depends_on = [google_project_service.apis]
}

resource "google_bigquery_table" "requests" {
  dataset_id          = google_bigquery_dataset.llmops.dataset_id
  table_id            = "requests"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "timestamp"
  }

  schema = jsonencode([
    { name = "timestamp",         type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "app_id",            type = "STRING",    mode = "REQUIRED" },
    { name = "session_id",        type = "STRING",    mode = "NULLABLE" },
    { name = "user_input",        type = "STRING",    mode = "REQUIRED" },
    { name = "output",            type = "STRING",    mode = "REQUIRED" },
    { name = "pipeline_executed", type = "STRING",    mode = "REQUIRED" },
    { name = "model",             type = "STRING",    mode = "REQUIRED" },
    { name = "prompt_version",    type = "STRING",    mode = "NULLABLE" },
    { name = "latency_ms",        type = "FLOAT",     mode = "REQUIRED" },
    { name = "input_length",      type = "INTEGER",   mode = "NULLABLE" },
    { name = "output_length",     type = "INTEGER",   mode = "NULLABLE" },
    { name = "needs_rag",         type = "BOOLEAN",   mode = "NULLABLE" },
    { name = "needs_agent",       type = "BOOLEAN",   mode = "NULLABLE" },
    { name = "retrieved_chunks",  type = "INTEGER",   mode = "NULLABLE" },
    { name = "guardrail_pass",    type = "BOOLEAN",   mode = "NULLABLE" },
  ])
}

resource "google_bigquery_table" "evaluation_results" {
  dataset_id          = google_bigquery_dataset.llmops.dataset_id
  table_id            = "evaluation_results"
  deletion_protection = false

  schema = jsonencode([
    { name = "timestamp",          type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "eval_run_id",        type = "STRING",    mode = "REQUIRED" },
    { name = "app_id",             type = "STRING",    mode = "REQUIRED" },
    { name = "request_timestamp",  type = "STRING",    mode = "NULLABLE" },
    { name = "user_input",         type = "STRING",    mode = "REQUIRED" },
    { name = "output",             type = "STRING",    mode = "REQUIRED" },
    { name = "pipeline_executed",  type = "STRING",    mode = "NULLABLE" },
    { name = "prompt_version",     type = "STRING",    mode = "NULLABLE" },
    { name = "model",              type = "STRING",    mode = "NULLABLE" },
    { name = "correctness_score",  type = "FLOAT",     mode = "NULLABLE" },
    { name = "relevance_score",    type = "FLOAT",     mode = "NULLABLE" },
    { name = "completeness_score", type = "FLOAT",     mode = "NULLABLE" },
    { name = "avg_score",          type = "FLOAT",     mode = "NULLABLE" },
    { name = "judge_model",        type = "STRING",    mode = "NULLABLE" },
    { name = "judge_explanation",  type = "STRING",    mode = "NULLABLE" },
  ])
}

resource "google_bigquery_table" "experiments" {
  dataset_id          = google_bigquery_dataset.llmops.dataset_id
  table_id            = "experiments"
  deletion_protection = false

  schema = jsonencode([
    { name = "timestamp",     type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "experiment_id", type = "STRING",    mode = "REQUIRED" },
    { name = "app_id",        type = "STRING",    mode = "REQUIRED" },
    { name = "model_a",       type = "STRING",    mode = "REQUIRED" },
    { name = "model_b",       type = "STRING",    mode = "REQUIRED" },
    { name = "avg_score_a",   type = "FLOAT",     mode = "NULLABLE" },
    { name = "avg_score_b",   type = "FLOAT",     mode = "NULLABLE" },
    { name = "winner",        type = "STRING",    mode = "NULLABLE" },
    { name = "promoted",      type = "BOOLEAN",   mode = "NULLABLE" },
    { name = "sample_size",   type = "INTEGER",   mode = "NULLABLE" },
  ])
}
