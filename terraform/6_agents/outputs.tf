output "pubsub_topic" {
  description = "Pub/Sub analysis jobs topic"
  value       = google_pubsub_topic.analysis_jobs.name
}

output "planner_subscription" {
  description = "Planner subscription"
  value       = google_pubsub_subscription.planner.name
}

output "agent_service_urls" {
  description = "Cloud Run URLs for each agent"
  value = merge(
    {
      planner = google_cloud_run_v2_service.planner.uri
    },
    {
      for name, svc in google_cloud_run_v2_service.workers : name => svc.uri
    }
  )
}

output "agents_service_account" {
  description = "Service account used by agents"
  value       = google_service_account.agents.email
}
