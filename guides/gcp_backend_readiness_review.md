# GCP Backend Architecture Conformance Review

Date: 2026-04-17

## Executive summary

The codebase is **partially migrated** and is **close to** a GCP architecture, but it is **not fully conformant yet** for clean backend testing.

- ✅ **Infrastructure as Code is GCP-first** in `terraform/*` (Google provider + Cloud Run + Pub/Sub + Cloud SQL + Monitoring).
- ✅ **Core model/runtime integration is GCP-first** in several backend paths (Vertex AI usage and Cloud SQL-compatible DB layer).
- ⚠️ **Significant AWS-era naming and runtime artifacts remain** (`lambda_handler.py`, `MOCK_LAMBDAS`, `Mangum`, guide docs still AWS).
- ⚠️ **Operational documentation is currently inconsistent** (guides still describe AWS deployments, which can mislead backend test setup).

## What already conforms to a GCP architecture

1. **Terraform provider and services are GCP-native**
   - Uses `hashicorp/google` provider across stacks.
   - Provisions Cloud Run, Pub/Sub, Cloud SQL, Cloud Storage, Cloud Scheduler, and Cloud Monitoring.

2. **Backend model path is Vertex-compatible**
   - Agents use `LitellmModel(model=f"vertex_ai/{model_id}")`.
   - Researcher service initializes Vertex AI and selects Gemini model.

3. **Database access layer is Cloud SQL-ready**
   - `DataAPIClient` is now a compatibility wrapper using SQLAlchemy + PostgreSQL rather than AWS Data API calls.

## Conformance gaps that should be resolved before backend testing

1. **Runtime naming/entrypoint confusion (high impact)**
   - Multiple services still expose `lambda_handler` function names and legacy comments.
   - This is workable, but increases risk of deployment/entrypoint mismatch in Cloud Run jobs/services.

2. **Mixed server adaptation layer in API service (high impact)**
   - API still imports/initializes `Mangum` (AWS Lambda adapter), while deployment target is Cloud Run.
   - If Cloud Run uses Uvicorn directly this may be harmless, but it is unnecessary and can confuse runtime assumptions.

3. **Legacy AWS terminology in code and env names (medium impact)**
   - Variables like `MOCK_LAMBDAS` and helper naming like `invoke_lambda_agent` remain.
   - These don’t always break execution, but complicate maintenance and troubleshooting on GCP.

4. **Guides/documentation are mostly AWS-focused (high operational impact)**
   - Current guides still instruct AWS services (Bedrock, Lambda, API Gateway, Aurora), while Terraform in repo is GCP.
   - This is likely to cause incorrect test environment setup.

## Backend testing readiness checklist (recommended before running full tests)

1. Ensure **all runtime env vars are GCP values** (project, region, Pub/Sub topic, Cloud SQL `DATABASE_URL`, Clerk JWKS).
2. Standardize each service entrypoint for Cloud Run (explicit ASGI app/start command).
3. Remove/rename AWS-specific runtime artifacts that can change behavior (`Mangum`, AWS-only handlers/flags).
4. Confirm queue payload contract between API publisher and planner consumer in Pub/Sub mode.
5. Run local smoke tests per backend service, then integration tests against deployed Cloud Run endpoints.

## Recommendation

Proceed with backend testing **only after a short cleanup pass** focused on entrypoints and runtime naming consistency. The architecture foundation is already GCP, but these leftover AWS artifacts create avoidable test failures and debugging noise.
