output "documents_bucket" {
  description = "Bucket used for ingestion documents"
  value       = google_storage_bucket.ingest_docs.name
}

output "ingest_service_url" {
  description = "Cloud Run URL for ingestion API"
  value       = google_cloud_run_v2_service.ingest.uri
}
