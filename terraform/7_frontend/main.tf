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
    "compute.googleapis.com",
    "run.googleapis.com",
    "storage.googleapis.com",
    "sqladmin.googleapis.com",
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

resource "google_compute_backend_bucket" "frontend" {
  count       = var.create_frontend_load_balancer ? 1 : 0
  name        = "alex-frontend-backend-bucket"
  project     = var.project_id
  bucket_name = google_storage_bucket.frontend.name
  enable_cdn  = true

  depends_on = [google_project_service.required]
}

resource "google_compute_managed_ssl_certificate" "frontend" {
  count   = var.create_frontend_load_balancer ? 1 : 0
  name    = "alex-frontend-cert"
  project = var.project_id

  managed {
    domains = [var.frontend_domain]
  }

  depends_on = [google_project_service.required]
}

resource "google_compute_url_map" "frontend_https" {
  count           = var.create_frontend_load_balancer ? 1 : 0
  name            = "alex-frontend-https-map"
  project         = var.project_id
  default_service = google_compute_backend_bucket.frontend[0].id
}

resource "google_compute_target_https_proxy" "frontend" {
  count            = var.create_frontend_load_balancer ? 1 : 0
  name             = "alex-frontend-https-proxy"
  project          = var.project_id
  url_map          = google_compute_url_map.frontend_https[0].id
  ssl_certificates = [google_compute_managed_ssl_certificate.frontend[0].id]
}

resource "google_compute_global_address" "frontend" {
  count   = var.create_frontend_load_balancer ? 1 : 0
  name    = "alex-frontend-ip"
  project = var.project_id
}

resource "google_compute_global_forwarding_rule" "frontend_https" {
  count                 = var.create_frontend_load_balancer ? 1 : 0
  name                  = "alex-frontend-https-forwarding-rule"
  project               = var.project_id
  ip_address            = google_compute_global_address.frontend[0].id
  port_range            = "443"
  target                = google_compute_target_https_proxy.frontend[0].id
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

resource "google_compute_url_map" "frontend_http_redirect" {
  count   = var.create_frontend_load_balancer ? 1 : 0
  name    = "alex-frontend-http-redirect-map"
  project = var.project_id

  default_url_redirect {
    https_redirect = true
    strip_query    = false
  }
}

resource "google_compute_target_http_proxy" "frontend_redirect" {
  count   = var.create_frontend_load_balancer ? 1 : 0
  name    = "alex-frontend-http-proxy"
  project = var.project_id
  url_map = google_compute_url_map.frontend_http_redirect[0].id
}

resource "google_compute_global_forwarding_rule" "frontend_http" {
  count                 = var.create_frontend_load_balancer ? 1 : 0
  name                  = "alex-frontend-http-forwarding-rule"
  project               = var.project_id
  ip_address            = google_compute_global_address.frontend[0].id
  port_range            = "80"
  target                = google_compute_target_http_proxy.frontend_redirect[0].id
  load_balancing_scheme = "EXTERNAL_MANAGED"
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

    volumes {
      name = "cloudsql"

      cloud_sql_instance {
        instances = [var.cloudsql_connection_name]
      }
    }

    containers {
      image = var.api_image

      env {
        name  = "DB_USER"
        value = var.db_user
      }
      env {
        name  = "DB_PASSWORD"
        value = var.db_password
      }
      env {
        name  = "DB_NAME"
        value = var.db_name
      }
      env {
        name  = "CLOUDSQL_CONNECTION_NAME"
        value = var.cloudsql_connection_name
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

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
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
