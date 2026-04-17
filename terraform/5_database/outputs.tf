output "cloud_sql_instance_name" {
  description = "Cloud SQL instance name"
  value       = google_sql_database_instance.alex_db.name
}

output "cloud_sql_public_ip" {
  description = "Cloud SQL public IPv4 address"
  value       = google_sql_database_instance.alex_db.public_ip_address
}

output "cloud_sql_connection_name" {
  description = "Cloud SQL instance connection name"
  value       = google_sql_database_instance.alex_db.connection_name
}

output "database_name" {
  description = "Database name"
  value       = google_sql_database.alex.name
}

output "db_user" {
  description = "Database username"
  value       = google_sql_user.alex_user.name
}

output "database_url_template" {
  description = "Connection string template for .env"
  sensitive   = true
  value       = "postgresql+psycopg2://${google_sql_user.alex_user.name}:<PASSWORD>@${google_sql_database_instance.alex_db.public_ip_address}:5432/${google_sql_database.alex.name}"
}
