variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "Vertex AI region"
  type        = string
  default     = "us-central1"
}

variable "create_matching_endpoint" {
  description = "Whether Terraform should create a Matching Engine endpoint"
  type        = bool
  default     = false
}

variable "matching_endpoint_name" {
  description = "Display name for Matching Engine endpoint"
  type        = string
  default     = "alex-matching-endpoint"
}
