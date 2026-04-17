terraform {
  required_version = ">= 1.6.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.40"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_project_service" "vertex" {
  project = var.project_id
  service = "aiplatform.googleapis.com"

  disable_on_destroy = false
}

resource "google_vertex_ai_index_endpoint" "matching_endpoint" {
  count        = var.create_matching_endpoint ? 1 : 0
  region       = var.region
  display_name = var.matching_endpoint_name
  project      = var.project_id

  depends_on = [google_project_service.vertex]
}
