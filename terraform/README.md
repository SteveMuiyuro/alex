# Alex Terraform (GCP)

This directory contains independent Terraform modules for each implementation phase on **GCP**.

## Module layout

- `2_sagemaker/` *(kept folder name for course continuity)*: Vertex AI API + optional Matching Engine endpoint
- `3_ingestion/`: Cloud Run ingestion service + GCS document bucket
- `4_researcher/`: Cloud Run researcher + optional Cloud Scheduler trigger
- `5_database/`: Cloud SQL PostgreSQL
- `6_agents/`: Pub/Sub orchestration + Cloud Run agent services
- `7_frontend/`: Cloud Run API + static frontend bucket
- `8_enterprise/`: Cloud Monitoring dashboard

## Design principles

1. **Independent state per module**
2. **Minimal managed services (no over-engineering)**
3. **Cloud-native GCP replacements for queue/runtime/monitoring**

## Typical workflow

```bash
cd terraform/5_database
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform apply
```

Repeat per module in order.

## Required environment variables (application runtime)

- `DATABASE_URL`
- `GOOGLE_CLOUD_PROJECT`
- `VERTEX_REGION`
- `VERTEX_MODEL`
- `PUBSUB_TOPIC`
- `CLERK_JWKS_URL` (API)

## Notes

- Cloud SQL is currently configured for **public IP + authorized networks** for dev speed.
- Recommended next hardening step: Cloud SQL private connectivity + Serverless VPC Access.
