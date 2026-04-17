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
  description = "Vertex region used for embeddings"
  type        = string
  default     = "us-east4"
}

variable "documents_bucket_name" {
  description = "Bucket for uploaded ingestion documents"
  type        = string
}

variable "ingest_image" {
  description = "Cloud Run ingestion image"
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "matching_engine_index_endpoint" {
  description = "Vertex Matching Engine index endpoint resource name"
  type        = string
  default     = ""
}

variable "matching_engine_index_id" {
  description = "Vertex Matching Engine index ID"
  type        = string
  default     = ""
}
