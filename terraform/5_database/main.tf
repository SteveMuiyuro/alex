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

resource "google_project_service" "sqladmin" {
  project = var.project_id
  service = "sqladmin.googleapis.com"

  disable_on_destroy = false
}

resource "google_sql_database_instance" "alex_db" {
  name             = var.instance_name
  project          = var.project_id
  region           = var.region
  database_version = "POSTGRES_15"

  settings {
    tier = var.tier

    ip_configuration {
      ipv4_enabled                                  = true
      private_network                               = null
      enable_private_path_for_google_cloud_services = false

      dynamic "authorized_networks" {
        for_each = var.authorized_networks
        content {
          name  = authorized_networks.value.name
          value = authorized_networks.value.cidr
        }
      }
    }

    backup_configuration {
      enabled = true
    }

    database_flags {
      name  = "cloudsql.iam_authentication"
      value = "on"
    }
  }

  deletion_protection = var.deletion_protection

  depends_on = [google_project_service.sqladmin]
}

resource "google_sql_database" "alex" {
  name     = var.database_name
  project  = var.project_id
  instance = google_sql_database_instance.alex_db.name
}

resource "google_sql_user" "alex_user" {
  name     = var.db_user
  project  = var.project_id
  instance = google_sql_database_instance.alex_db.name
  password = var.db_password
}
