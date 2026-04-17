variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "Primary GCP region"
  type        = string
  default     = "us-central1"
}

variable "instance_name" {
  description = "Cloud SQL instance name"
  type        = string
  default     = "alex-db"
}

variable "database_name" {
  description = "Application database name"
  type        = string
  default     = "alex"
}

variable "db_user" {
  description = "Cloud SQL database user"
  type        = string
  default     = "alex_app"
}

variable "db_password" {
  description = "Cloud SQL database password"
  type        = string
  sensitive   = true
}

variable "tier" {
  description = "Cloud SQL machine tier"
  type        = string
  default     = "db-custom-1-3840"
}

variable "deletion_protection" {
  description = "Protect Cloud SQL from accidental deletion"
  type        = bool
  default     = true
}

variable "authorized_networks" {
  description = "Public CIDR allowlist entries"
  type = list(object({
    name = string
    cidr = string
  }))
  default = []
}
