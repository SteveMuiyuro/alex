variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "Cloud Run deployment region"
  type        = string
  default     = "us-central1"
}

variable "vertex_region" {
  description = "Vertex AI region"
  type        = string
  default     = "us-east4"
}

variable "vertex_model" {
  description = "Vertex AI Gemini model"
  type        = string
  default     = "gemini-2.5-flash"
}

variable "database_url" {
  description = "PostgreSQL SQLAlchemy connection URL"
  type        = string
  sensitive   = true
}

variable "default_agent_image" {
  description = "Default container image for agents"
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "agent_images" {
  description = "Optional per-agent image overrides"
  type        = map(string)
  default     = {}
}
