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

locals {
  worker_agent_names = ["tagger", "reporter", "charter", "retirement"]
}

resource "google_project_service" "required" {
  for_each = toset([
    "run.googleapis.com",
    "pubsub.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
  ])
  project = var.project_id
  service = each.value

  disable_on_destroy = false
}

resource "google_pubsub_topic" "analysis_jobs" {
  name    = "alex-analysis-jobs"
  project = var.project_id
}

resource "google_pubsub_subscription" "planner" {
  name    = "alex-planner-sub"
  topic   = google_pubsub_topic.analysis_jobs.name
  project = var.project_id

  ack_deadline_seconds = 60

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.planner.uri}/pubsub/push"
  }
}

resource "google_service_account" "agents" {
  account_id   = "alex-agents-sa"
  display_name = "Alex Agents Runtime"
  project      = var.project_id
}

resource "google_project_iam_member" "agents_roles" {
  for_each = toset([
    "roles/pubsub.subscriber",
    "roles/pubsub.publisher",
    "roles/cloudsql.client",
    "roles/aiplatform.user",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.agents.email}"
}

resource "google_cloud_run_v2_service" "workers" {
  for_each = toset(local.worker_agent_names)

  name     = "alex-${each.value}"
  project  = var.project_id
  location = var.region

  ingress = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.agents.email

    containers {
      image = lookup(var.agent_images, each.value, var.default_agent_image)

      env {
        name  = "AGENT_NAME"
        value = each.value
      }
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
        name  = "PUBSUB_TOPIC"
        value = google_pubsub_topic.analysis_jobs.name
      }
      env {
        name  = "DATABASE_URL"
        value = var.database_url
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_cloud_run_v2_service" "planner" {
  name     = "alex-planner"
  project  = var.project_id
  location = var.region

  ingress = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.agents.email

    containers {
      image = lookup(var.agent_images, "planner", var.default_agent_image)

      env {
        name  = "AGENT_NAME"
        value = "planner"
      }
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
        name  = "PUBSUB_TOPIC"
        value = google_pubsub_topic.analysis_jobs.name
      }
      env {
        name  = "DATABASE_URL"
        value = var.database_url
      }
      env {
        name  = "TAGGER_ENDPOINT"
        value = "${google_cloud_run_v2_service.workers["tagger"].uri}/tag"
      }
      env {
        name  = "REPORTER_ENDPOINT"
        value = "${google_cloud_run_v2_service.workers["reporter"].uri}/report"
      }
      env {
        name  = "CHARTER_ENDPOINT"
        value = "${google_cloud_run_v2_service.workers["charter"].uri}/chart"
      }
      env {
        name  = "RETIREMENT_ENDPOINT"
        value = "${google_cloud_run_v2_service.workers["retirement"].uri}/retirement"
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }
  }

  depends_on = [google_project_service.required, google_cloud_run_v2_service.workers]
}

resource "google_cloud_run_v2_service_iam_member" "planner_public_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.planner.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "worker_public_invokers" {
  for_each = google_cloud_run_v2_service.workers

  project  = var.project_id
  location = var.region
  name     = each.value.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
