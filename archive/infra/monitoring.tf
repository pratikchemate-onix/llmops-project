# Alert: backend latency > 5 seconds (p95)
resource "google_monitoring_alert_policy" "high_latency" {
  display_name     = "LLMOps — High Latency"
  combiner         = "OR"

  conditions {
    display_name = "Cloud Run request latency > 5s"
    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"llmops-backend\" AND metric.type=\"run.googleapis.com/request_latencies\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 5000
      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_PERCENTILE_95"
        cross_series_reducer = "REDUCE_MEAN"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.name]
  severity              = "WARNING"
}

# Alert: backend error rate > 5%
resource "google_monitoring_alert_policy" "high_error_rate" {
  display_name = "LLMOps — High Error Rate"
  combiner     = "OR"

  conditions {
    display_name = "Cloud Run 5xx error rate > 5%"
    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"llmops-backend\" AND metric.type=\"run.googleapis.com/request_count\" AND metric.labels.response_code_class=\"5xx\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0.05
      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.name]
  severity = "ERROR"
}

# Notification channel (email) — fill in your email
resource "google_monitoring_notification_channel" "email" {
  display_name = "LLMOps Email Alerts"
  type         = "email"

  labels = {
    email_address = var.alert_email
  }
}

variable "alert_email" {
  description = "Email address for monitoring alerts"
  type        = string
  default     = "your-email@company.com"
}
