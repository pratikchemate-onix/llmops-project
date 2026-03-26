# Document storage bucket (uploads trigger RAG ingestion)
resource "google_storage_bucket" "llmops_docs" {
  name          = "${var.project_id}-llmops-docs"
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true

  versioning { enabled = true }

  lifecycle_rule {
    condition { age = 365 }
    action    { type = "Delete" }
  }
}

# Pipeline artifacts bucket (KFP needs this to store intermediate results)
resource "google_storage_bucket" "pipeline_artifacts" {
  name          = "${var.project_id}-llmops-pipeline-artifacts"
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true

  versioning { enabled = false }

  lifecycle_rule {
    condition { age = 30 }
    action    { type = "Delete" }
  }
}

# Test sets bucket (for experiment pipeline test questions)
resource "google_storage_bucket" "test_sets" {
  name          = "${var.project_id}-llmops-test-sets"
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true
}

output "docs_bucket" {
  value = google_storage_bucket.llmops_docs.name
}

output "pipeline_root" {
  value = "gs://${google_storage_bucket.pipeline_artifacts.name}"
}
