# Alex Gameplan (GCP Source of Truth)

Date: 2026-04-17

This document is the GCP execution plan for Alex. It translates legacy AWS guide concepts into the GCP architecture currently implemented in this repository.

## 1) Target GCP Architecture

- **Compute**: Cloud Run services (`alex-api`, `alex-ingest`, `alex-researcher`, `alex-planner`, `alex-tagger`, `alex-reporter`, `alex-charter`, `alex-retirement`)
- **Queue**: Pub/Sub topic + subscription (`alex-analysis-jobs`, `alex-planner-sub`)
- **Database**: Cloud SQL PostgreSQL
- **AI Models**: Vertex AI (Gemini + embedding path)
- **Storage**: Cloud Storage (documents + static frontend assets)
- **Scheduling**: Cloud Scheduler (`alex-research-schedule`)
- **Observability**: Cloud Logging + Cloud Monitoring dashboard

## 2) Progress-Based Plan

### Completed (assumed)
- Up through database provisioning and schema readiness.

### Next critical milestone
- **Working backend API** on Cloud Run.

A “working backend API” means:
1. Health endpoint responds.
2. Protected endpoints validate Clerk JWT.
3. API reads/writes Cloud SQL successfully.
4. API publishes job messages to Pub/Sub.
5. Planner consumes and updates job status/results in DB.

## 3) AWS→GCP Translation Table

| Legacy AWS concept | GCP implementation |
|---|---|
| Lambda (API + agents) | Cloud Run services |
| API Gateway | Cloud Run HTTPS endpoint (optionally add GCP API Gateway later) |
| SQS | Pub/Sub topic/subscription |
| Aurora PostgreSQL | Cloud SQL PostgreSQL |
| Bedrock / SageMaker | Vertex AI |
| EventBridge | Cloud Scheduler |
| CloudWatch | Cloud Logging + Cloud Monitoring |
| S3 / CloudFront | Cloud Storage static hosting (+ optional Cloud CDN) |

## 4) GCP Console Checklist for Backend API

## Step A — API
In **APIs & Services**, enable:
- Cloud Run API
- Artifact Registry API
- Cloud Build API
- Pub/Sub API
- Cloud SQL Admin API
- Vertex AI API
- Cloud Logging API
- Cloud Monitoring API

## Step B — Cloud SQL
In **SQL**:
1. Confirm instance is `RUNNABLE`.
2. Confirm database/user exist.
3. Confirm you have host (public IP or private routing).
4. Build `DATABASE_URL` and store securely.

## Step C — Pub/Sub
In **Pub/Sub**:
1. Confirm topic `alex-analysis-jobs` exists.
2. Confirm subscription `alex-planner-sub` exists.

## Step D — Cloud Run API service
In **Cloud Run → alex-api → Edit and deploy new revision**, set env vars:
- `DATABASE_URL`
- `PUBSUB_TOPIC=alex-analysis-jobs`
- `CLERK_JWKS_URL`
- `GOOGLE_CLOUD_PROJECT`
- `VERTEX_REGION` (ex: `us-east4`)
- `VERTEX_MODEL` (ex: `gemini-2.5-flash`)

Then deploy revision.

## Step E — API service account permissions
In **IAM** ensure API service account has:
- `roles/cloudsql.client`
- `roles/pubsub.publisher`
- `roles/aiplatform.user`
- `roles/logging.logWriter`
- `roles/monitoring.metricWriter`

## Step F — Planner and agent services
In **Cloud Run**, confirm deployed and healthy:
- `alex-planner`
- `alex-tagger`
- `alex-reporter`
- `alex-charter`
- `alex-retirement`

Planner service account needs:
- `roles/pubsub.subscriber`
- `roles/pubsub.publisher`
- `roles/cloudsql.client`
- `roles/aiplatform.user`
- logging/monitoring writer roles

## Step G — Smoke test chain
1. Call `alex-api` health endpoint.
2. Create/get user via API.
3. Trigger analysis request endpoint (publishes to Pub/Sub).
4. Observe planner log consumption from subscription.
5. Verify DB job status transitions to `running/completed`.

## 5) Terraform Directory Guidance (GCP)

Use these in order after DB stage:

1. `terraform/6_agents` (queue + agent services)
2. `terraform/7_frontend` (includes API service + frontend bucket)
3. `terraform/8_enterprise` (monitoring dashboard)

If ingestion/research not yet deployed on GCP, apply:
- `terraform/3_ingestion`
- `terraform/4_researcher`

## 6) Known GCP-Phase Cleanup (recommended)

Not mandatory for first success, but recommended:
1. Rename AWS-legacy runtime labels (`lambda_handler`, `MOCK_LAMBDAS`) to Cloud Run-neutral names.
2. Remove AWS Lambda adapter (`Mangum`) if fully Cloud Run-native.
3. Consolidate env docs into one `.env.gcp.example` source.

## 7) Ready-to-Proceed Gate

Proceed to frontend integration only when all are true:
- `alex-api` healthy + auth working.
- API CRUD against Cloud SQL works.
- API publishes queue jobs.
- Planner consumes jobs and specialist agents complete writes.
- Monitoring/logs show stable end-to-end backend execution.
