variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "Primary region"
  type        = string
  default     = "us-central1"
}

variable "dashboard_name" {
  description = "Cloud Monitoring dashboard name"
  type        = string
  default     = "alex-enterprise-observability"
}
