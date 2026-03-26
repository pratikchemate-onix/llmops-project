# Topic for GCS document upload events
resource "google_pubsub_topic" "doc_uploads" {
  name = "llmops-doc-uploads"
}

# GCS sends notifications to this topic when files are uploaded
resource "google_storage_notification" "doc_uploads" {
  bucket         = google_storage_bucket.llmops_docs.name
  payload_format = "JSON_API_V1"
  topic          = google_pubsub_topic.doc_uploads.id
  event_types    = ["OBJECT_FINALIZE"]

  depends_on = [google_pubsub_topic_iam_member.gcs_publisher]
}

# Allow GCS service account to publish to the topic
data "google_storage_project_service_account" "gcs_sa" {}

resource "google_pubsub_topic_iam_member" "gcs_publisher" {
  topic  = google_pubsub_topic.doc_uploads.id
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${data.google_storage_project_service_account.gcs_sa.email_address}"
}
