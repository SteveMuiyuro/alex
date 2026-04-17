output "frontend_bucket" {
  description = "Frontend static bucket"
  value       = google_storage_bucket.frontend.name
}

output "frontend_website_url" {
  description = "Static website endpoint"
  value       = "https://storage.googleapis.com/${google_storage_bucket.frontend.name}/index.html"
}

output "frontend_load_balancer_ip" {
  description = "Reserved global IP for the frontend load balancer. Point your frontend domain A record here."
  value       = var.create_frontend_load_balancer ? google_compute_global_address.frontend[0].address : null
}

output "frontend_custom_domain_url" {
  description = "Custom domain URL for the frontend, if configured."
  value       = var.create_frontend_load_balancer ? "https://${var.frontend_domain}" : null
}

output "api_url" {
  description = "Cloud Run API URL"
  value       = google_cloud_run_v2_service.api.uri
}

output "api_service_account" {
  description = "Service account used by API"
  value       = google_service_account.api.email
}
