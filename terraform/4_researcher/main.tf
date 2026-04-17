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
    "cloudscheduler.googleapis.com",
    "aiplatform.googleapis.com",
  ])
  project = var.project_id
  service = each.value

  disable_on_destroy = false
}

resource "google_service_account" "researcher" {
  account_id   = "alex-researcher-sa"
  display_name = "Alex Researcher Service"
  project      = var.project_id
}

resource "google_project_iam_member" "researcher_roles" {
  for_each = toset([
    "roles/aiplatform.user",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.researcher.email}"
}

resource "google_cloud_run_v2_service" "researcher" {
  name     = "alex-researcher"
  project  = var.project_id
  location = var.region

  ingress = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.researcher.email

    containers {
      image = var.researcher_image

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "VERTEX_REGION"
        value = var.vertex_region
      }
      env {
        name  = "VERTEX_MODEL"
        value = var.vertex_model
      }
      env {
        name  = "INGEST_SERVICE_URL"
        value = var.ingest_service_url
      }
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_cloud_run_v2_service_iam_member" "invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.researcher.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_scheduler_job" "research_schedule" {
  count    = var.enable_scheduler ? 1 : 0
  project  = var.project_id
  region   = var.region
  name     = "alex-research-schedule"
  schedule = var.schedule_cron

  http_target {
    uri         = "${google_cloud_run_v2_service.researcher.uri}/research/auto"
    http_method = "POST"
  }
}
