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
  ])
  project = var.project_id
  service = each.value

  disable_on_destroy = false
}

resource "google_storage_bucket" "frontend" {
  name                        = var.frontend_bucket_name
  location                    = var.region
  project                     = var.project_id
  force_destroy               = true
  uniform_bucket_level_access = true
  website {
    main_page_suffix = "index.html"
    not_found_page   = "index.html"
  }
}

resource "google_storage_bucket_iam_member" "public_read" {
  bucket = google_storage_bucket.frontend.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

resource "google_service_account" "api" {
  account_id   = "alex-api-sa"
  display_name = "Alex API Service Account"
  project      = var.project_id
}

resource "google_project_iam_member" "api_roles" {
  for_each = toset([
    "roles/cloudsql.client",
    "roles/pubsub.publisher",
    "roles/aiplatform.user",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_cloud_run_v2_service" "api" {
  name     = "alex-api"
  project  = var.project_id
  location = var.region

  ingress = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.api.email

    containers {
      image = var.api_image

      env {
        name  = "DATABASE_URL"
        value = var.database_url
      }
      env {
        name  = "PUBSUB_TOPIC"
        value = var.pubsub_topic
      }
      env {
        name  = "CLERK_JWKS_URL"
        value = var.clerk_jwks_url
      }
      env {
        name  = "VERTEX_MODEL"
        value = var.vertex_model
      }
      env {
        name  = "VERTEX_REGION"
        value = var.vertex_region
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
