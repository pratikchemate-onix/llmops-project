# Nightly evaluation for each app (2am IST = 8:30pm UTC)
locals {
  apps_to_evaluate = ["default_llm", "rag_bot", "code_agent"]
}

resource "google_cloud_scheduler_job" "nightly_eval" {
  for_each = toset(local.apps_to_evaluate)

  name        = "llmops-eval-${each.key}"
  description = "Nightly evaluation for ${each.key}"
  schedule    = "30 20 * * *"  # 2am IST daily
  time_zone   = "Asia/Kolkata"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-aiplatform.googleapis.com/v1/projects/${var.project_id}/locations/${var.region}/pipelineJobs"
    
    body = base64encode(jsonencode({
      displayName  = "nightly-eval-${each.key}"
      templateUri  = "gs://${google_storage_bucket.pipeline_artifacts.name}/pipelines/evaluation_pipeline.json"
      pipelineRoot = "gs://${google_storage_bucket.pipeline_artifacts.name}"
      parameterValues = {
        app_id     = each.key
        project_id = var.project_id
      }
    }))

    oauth_token {
      service_account_email = google_service_account.backend_sa.email
    }
  }

  depends_on = [google_project_service.apis]
}

# Grant additional roles to the Backend SA so it can run pipelines
# It already has Vertex AI User and Secret Accessor from main.tf

resource "google_project_iam_member" "backend_bq_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.backend_sa.email}"
}

resource "google_project_iam_member" "backend_firestore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.backend_sa.email}"
}

resource "google_project_iam_member" "backend_storage_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.backend_sa.email}"
}
