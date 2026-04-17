output "researcher_service_url" {
  description = "Researcher Cloud Run URL"
  value       = google_cloud_run_v2_service.researcher.uri
}

output "research_scheduler_name" {
  description = "Cloud Scheduler job name (if enabled)"
  value       = try(google_cloud_scheduler_job.research_schedule[0].name, null)
}
