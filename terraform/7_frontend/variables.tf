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

variable "db_user" {
  description = "PostgreSQL username"
  type        = string
}

variable "db_password" {
  description = "PostgreSQL password"
  type        = string
  sensitive   = true
}

variable "db_name" {
  description = "PostgreSQL database name"
  type        = string
}

variable "cloudsql_connection_name" {
  description = "Cloud SQL instance connection name"
  type        = string
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

variable "create_frontend_load_balancer" {
  description = "Whether to create a global external HTTPS load balancer for the static frontend."
  type        = bool
  default     = false
}

variable "frontend_domain" {
  description = "Custom domain for the frontend, e.g. app.example.com. Required when create_frontend_load_balancer is true."
  type        = string
  default     = ""

  validation {
    condition     = var.create_frontend_load_balancer == false || length(trimspace(var.frontend_domain)) > 0
    error_message = "frontend_domain must be set when create_frontend_load_balancer is true."
  }
}
