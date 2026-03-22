


terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "asia-south1"
}

# Enable required APIs
# Added aiplatform.googleapis.com for Vertex AI
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudbuild.googleapis.com",
    "aiplatform.googleapis.com", 
  ])
  service            = each.key
  disable_on_destroy = false
}

# Artifact Registry for Docker images
resource "google_artifact_registry_repository" "llmops" {
  repository_id = "llmops-repo"
  format        = "DOCKER"
  location      = var.region
  description   = "LLMOps pipeline Docker images"
  depends_on    = [google_project_service.apis]
}

# Secret: Anthropic API Key (Gemini uses Vertex AI, no key needed)
resource "google_secret_manager_secret" "anthropic_api_key" {
  secret_id = "ANTHROPIC_API_KEY"
  replication { auto {} }
  depends_on = [google_project_service.apis]
}

# ---------------------------------------------------------
# 1. CI/CD Service Account (Deployer)
# ---------------------------------------------------------
resource "google_service_account" "github_actions" {
  account_id   = "github-actions-deploy"
  display_name = "GitHub Actions Deploy SA"
}

# IAM: allow SA to deploy Cloud Run and push images
resource "google_project_iam_member" "github_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.github_actions.email}"
}

resource "google_project_iam_member" "github_registry_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.github_actions.email}"
}

resource "google_project_iam_member" "github_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.github_actions.email}"
}

resource "google_project_iam_member" "github_sa_user" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${google_service_account.github_actions.email}"
}

# ---------------------------------------------------------
# 2. Runtime Service Account (The App itself)
# ---------------------------------------------------------
resource "google_service_account" "backend_sa" {
  account_id   = "llmops-backend-sa"
  display_name = "LLMOps Backend Runtime SA"
}

# Grant Vertex AI User role to the Runtime SA so it can call Gemini
resource "google_project_iam_member" "backend_vertex_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.backend_sa.email}"
}

# Grant Secret Accessor to Runtime SA (to read Anthropic key)
resource "google_project_iam_member" "backend_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.backend_sa.email}"
}

output "artifact_registry_url" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/llmops-repo"
}

output "github_sa_email" {
  value = google_service_account.github_actions.email
}

output "backend_sa_email" {
  value = google_service_account.backend_sa.email
}
