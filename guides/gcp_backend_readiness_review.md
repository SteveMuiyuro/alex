# Alex on GCP: Console Implementation Runbook (Backend-First)

Date: 2026-04-17

This is the practical plan to replicate the Alex architecture on GCP (AWS terms in older guides are treated as reference only).

## 1) AWS → GCP service mapping (what we are implementing)

| Original concept | GCP equivalent in this repo |
|---|---|
| Lambda functions | Cloud Run services |
| API Gateway | Cloud Run API endpoint (optionally behind API Gateway later) |
| SQS | Pub/Sub topic + subscription |
| Aurora PostgreSQL | Cloud SQL for PostgreSQL |
| SageMaker embeddings | Vertex AI embeddings / Vertex model calls |
| Bedrock LLM | Vertex Gemini via LiteLLM (`vertex_ai/...`) |
| EventBridge schedule | Cloud Scheduler job |
| CloudWatch dashboard | Cloud Monitoring dashboard |
| S3 static hosting + CloudFront | Cloud Storage static website (optionally add Cloud CDN later) |

Evidence this repo is already scaffolded for GCP infrastructure is in Terraform stacks using the Google provider and GCP services. See `terraform/3_ingestion`, `terraform/4_researcher`, `terraform/5_database`, `terraform/6_agents`, `terraform/7_frontend`, and `terraform/8_enterprise`.

---

## 2) What to do in the GCP Console (exact order)

## Step A — Create/select project + set billing

1. Open **GCP Console** → Project picker → **New Project** (or choose existing).
2. Open **Billing** and make sure billing is linked.
3. Decide regions now and keep consistent:
   - App region: `us-central1` (Cloud Run + Cloud SQL)
   - Vertex region: `us-east4` (as currently used by code defaults)

## Step B — Enable required APIs

Open **APIs & Services → Enabled APIs → Enable APIs and Services** and enable:

- Cloud Run API
- Artifact Registry API
- Cloud Build API
- Pub/Sub API
- Cloud SQL Admin API
- Cloud Scheduler API
- Vertex AI API
- Cloud Storage API
- Cloud Monitoring API

(These also align with the Terraform `google_project_service` resources.)

## Step C — Create Artifact Registry repos and push images

1. Open **Artifact Registry → Repositories → Create Repository**.
2. Create Docker repos you want to use for images (example names):
   - `alex-backend`
   - `alex-agents`
   - `alex-researcher`
3. Build and push each service image from local/dev environment and record full image URLs.

You need image URLs for:
- ingest service
- researcher service
- api service
- planner/tagger/reporter/charter/retirement (or one default image if multiplexed)

## Step D — Provision Cloud SQL (database)

1. Open **SQL → Create instance → PostgreSQL**.
2. Instance name should match your tfvars intent (default `alex-db`).
3. Pick region (`us-central1` recommended for app workloads).
4. Create database `alex` and app user (default in Terraform is `alex_app`).
5. Record:
   - Public IP (or private connectivity details)
   - DB user
   - DB password
   - Database name
6. Build `DATABASE_URL` for services:
   - `postgresql+psycopg2://USER:PASSWORD:HOST:5432/DBNAME`

## Step E — Set up ingestion storage + vector settings

1. Open **Cloud Storage → Buckets → Create**.
2. Create ingestion bucket (name must be globally unique).
3. Keep bucket name for Terraform `documents_bucket_name`.
4. If using Vertex Matching Engine, create endpoint/index resources and capture IDs (optional in this repo, can be blank initially).

## Step F — Set up async orchestration (Pub/Sub)

1. Open **Pub/Sub → Topics → Create topic** named `alex-analysis-jobs`.
2. Open topic and create subscription `alex-planner-sub`.
3. Keep topic name for API service env (`PUBSUB_TOPIC`).

## Step G — Deploy backend services (Cloud Run)

Deploy in this order (via Terraform directories):

1. `terraform/3_ingestion`
2. `terraform/4_researcher`
3. `terraform/5_database` (if not already done manually)
4. `terraform/6_agents`
5. `terraform/7_frontend` (for API service and static bucket)
6. `terraform/8_enterprise`

In Console, verify each Cloud Run service exists and is healthy:

- `alex-ingest`
- `alex-researcher`
- `alex-planner`
- `alex-tagger`
- `alex-reporter`
- `alex-charter`
- `alex-retirement`
- `alex-api`

## Step H — Configure runtime environment variables in Cloud Run

For each service, open **Cloud Run → Service → Edit and deploy new revision → Variables & Secrets**.

Core env values to set/verify:

- `GOOGLE_CLOUD_PROJECT`
- `VERTEX_REGION` (e.g., `us-east4`)
- `VERTEX_MODEL` (e.g., `gemini-2.5-flash`)
- `DATABASE_URL`
- `PUBSUB_TOPIC` (for API/planner paths)
- `CLERK_JWKS_URL` (API auth)
- Service-to-service URLs where needed (reporter/charter/retirement/tagger endpoints)

## Step I — IAM in Console (minimum required)

Open **IAM & Admin → IAM** and verify service accounts have these roles (as scaffolded by Terraform):

- Agents SA:
  - Pub/Sub Subscriber
  - Pub/Sub Publisher
  - Cloud SQL Client
  - Vertex AI User
  - Logging Writer
  - Monitoring Metric Writer
- API SA:
  - Cloud SQL Client
  - Pub/Sub Publisher
  - Vertex AI User
  - Logging Writer
  - Monitoring Metric Writer
- Ingest/Researcher SAs:
  - Vertex AI User
  - Logging Writer
  - (plus Storage access for ingest)

## Step J — Observability and scheduler

1. Open **Monitoring → Dashboards** and confirm enterprise dashboard exists.
2. Open **Scheduler** and confirm `alex-research-schedule` if enabled.
3. Open **Logs Explorer** and filter by Cloud Run service names while testing.

---

## 3) Backend test gate (do this before full tests)

You are ready to run backend integration tests when all are true:

- Cloud Run services above are deployed and return healthy checks.
- API can publish a test message to `alex-analysis-jobs`.
- Planner consumes from `alex-planner-sub` and updates a real job record in DB.
- Agents can reach DB via `DATABASE_URL` and call Vertex model successfully.
- Clerk token verification works on `/api/*` routes.

---

## 4) Known code cleanup items to avoid friction (recommended)

These are not blockers for architecture replication, but they reduce confusion:

1. Rename legacy AWS-oriented function names (`lambda_handler`, `MOCK_LAMBDAS`) to neutral runtime names.
2. Remove Lambda adapter imports (`Mangum`) if you are fully Cloud Run-native.
3. Keep one canonical `.env` template for GCP values to avoid mixed AWS/GCP variables.

---

## 5) Fast start for your next session

When you open Console next, do this first:

1. Check APIs enabled.
2. Check Cloud SQL is `RUNNABLE`.
3. Check Pub/Sub topic/subscription exist.
4. Check all 8 Cloud Run services are deployed.
5. Trigger one analysis request from API and watch logs in Cloud Run + Pub/Sub.

If you want, next I can generate a **single copy/paste “GCP console checklist”** you can tick off line-by-line while deploying.
