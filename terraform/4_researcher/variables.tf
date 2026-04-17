variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "vertex_region" {
  description = "Vertex region"
  type        = string
  default     = "us-east4"
}

variable "vertex_model" {
  description = "Vertex model"
  type        = string
  default     = "gemini-2.5-flash"
}

variable "researcher_image" {
  description = "Researcher Cloud Run image"
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "ingest_service_url" {
  description = "Ingestion service URL"
  type        = string
  default     = ""
}

variable "enable_scheduler" {
  description = "Enable periodic automated research"
  type        = bool
  default     = false
}

variable "schedule_cron" {
  description = "Cloud Scheduler cron expression"
  type        = string
  default     = "0 */2 * * *"
}
