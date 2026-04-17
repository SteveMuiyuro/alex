output "dashboard_id" {
  description = "Cloud Monitoring dashboard ID"
  value       = google_monitoring_dashboard.enterprise.id
}

output "dashboard_name" {
  description = "Cloud Monitoring dashboard display name"
  value       = var.dashboard_name
}
