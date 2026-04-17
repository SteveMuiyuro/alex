output "frontend_bucket" {
  description = "Frontend static bucket"
  value       = google_storage_bucket.frontend.name
}

output "frontend_website_url" {
  description = "Static website endpoint"
  value       = "https://storage.googleapis.com/${google_storage_bucket.frontend.name}/index.html"
}

output "api_url" {
  description = "Cloud Run API URL"
  value       = google_cloud_run_v2_service.api.uri
}

output "api_service_account" {
  description = "Service account used by API"
  value       = google_service_account.api.email
}
