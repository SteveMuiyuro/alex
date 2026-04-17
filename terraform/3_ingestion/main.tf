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

resource "google_project_service" "required" {
  for_each = toset([
    "run.googleapis.com",
    "storage.googleapis.com",
    "aiplatform.googleapis.com",
  ])
  project = var.project_id
  service = each.value

  disable_on_destroy = false
}

resource "google_storage_bucket" "ingest_docs" {
  name          = var.documents_bucket_name
  project       = var.project_id
  location      = var.region
  force_destroy = true
}

resource "google_service_account" "ingest" {
  account_id   = "alex-ingest-sa"
  display_name = "Alex Ingestion Service"
  project      = var.project_id
}

resource "google_project_iam_member" "ingest_roles" {
  for_each = toset([
    "roles/storage.objectAdmin",
    "roles/aiplatform.user",
    "roles/logging.logWriter",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.ingest.email}"
}

resource "google_cloud_run_v2_service" "ingest" {
  name     = "alex-ingest"
  project  = var.project_id
  location = var.region

  ingress = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.ingest.email

    containers {
      image = var.ingest_image

      env {
        name  = "DOCUMENTS_BUCKET"
        value = google_storage_bucket.ingest_docs.name
      }
      env {
        name  = "VERTEX_REGION"
        value = var.vertex_region
      }
      env {
        name  = "MATCHING_ENGINE_INDEX_ENDPOINT"
        value = var.matching_engine_index_endpoint
      }
      env {
        name  = "MATCHING_ENGINE_INDEX_ID"
        value = var.matching_engine_index_id
      }
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.ingest.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
