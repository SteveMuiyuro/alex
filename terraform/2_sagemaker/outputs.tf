output "vertex_region" {
  description = "Vertex AI region"
  value       = var.region
}

output "matching_endpoint_id" {
  description = "Matching Engine endpoint ID (if created)"
  value       = try(google_vertex_ai_index_endpoint.matching_endpoint[0].id, null)
}
