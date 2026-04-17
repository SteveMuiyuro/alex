variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "frontend_bucket_name" {
  description = "Static frontend bucket name"
  type        = string
}

variable "api_image" {
  description = "Cloud Run API container image"
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "database_url" {
  description = "PostgreSQL SQLAlchemy URL"
  type        = string
  sensitive   = true
}

variable "pubsub_topic" {
  description = "Pub/Sub topic for analysis jobs"
  type        = string
}

variable "clerk_jwks_url" {
  description = "Clerk JWKS URL"
  type        = string
}

variable "vertex_model" {
  description = "Vertex model used by API/orchestrator"
  type        = string
  default     = "gemini-2.5-flash"
}

variable "vertex_region" {
  description = "Vertex region"
  type        = string
  default     = "us-east4"
}
