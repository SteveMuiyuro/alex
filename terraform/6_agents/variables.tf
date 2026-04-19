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

variable "openai_api_secret_name" {
  description = "Secret Manager secret name for the OpenAI API key"
  type        = string
}

variable "langfuse_public_key_secret_name" {
  description = "Optional Secret Manager secret name for the Langfuse public key"
  type        = string
  default     = ""
}

variable "langfuse_secret_key_secret_name" {
  description = "Optional Secret Manager secret name for the Langfuse secret key"
  type        = string
  default     = ""
}

variable "langfuse_base_url" {
  description = "Optional Langfuse base URL/host"
  type        = string
  default     = ""
}

variable "polygon_api_key_secret_name" {
  description = "Optional Secret Manager secret name for the Polygon API key"
  type        = string
  default     = ""
}

variable "polygon_plan" {
  description = "Polygon plan type used by the planner service"
  type        = string
  default     = "free"
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
