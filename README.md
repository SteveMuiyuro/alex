# Alex - the Agentic Learning Equities Explainer

## Multi-agent Enterprise-Grade SaaS Financial Planner

![Course Image](assets/alex.png)

_If you're looking at this in Cursor, please right click on the filename in the Explorer on the left, and select "Open preview", to view it in formatted glory._

### Welcome to The Capstone Project for Week 3 and Week 4!

#### The directories:

1. **guides** - this is where you will live - step by step guides to deploy to production
2. **backend** - the agent code, organized into subdirectories, each a uv project (as is the backend parent directory)
3. **frontend** - a NextJS React frontend integrated with Clerk
4. **terraform** - separate terraform subdirectories with state for each part
5. **scripts** - the final deployment script

#### Order of play:

##### Week 3

- On Week 3 Day 3, we will do 1_permissions and 2_sagemaker
- On Week 3 Day 4, we will do 3_ingest
- On Week 3 Day 5, we will do 4_researcher

##### Week 4

- On Week 4 Day 1, we will do 5_database
- On Week 4 Day 2, we will do 6_agents
- On Week 4 Day 3, we will do 7_frontend
- On Week 4 Day 4, we will do 8_enterprise

#### Keep in mind

- Please submit your community_contributions, including links to your repos, in the production repo community_contributions folder
- Regularly do a git pull to get the latest code
- Reach out in Udemy or email (ed@edwarddonner.com) if I can help! This is a gigantic project and I am here to help you deliver it!

#### Quick pre-flight checklist (before running deploy/package scripts)

- Confirm Docker Desktop is running and healthy (`docker ps` should work).
- Confirm you are using the intended AWS account and region (`aws sts get-caller-identity` and `aws configure list`).
- In each Terraform folder, copy `terraform.tfvars.example` to `terraform.tfvars` and fill all required variables before `terraform apply`.
- Use `uv` for Python commands in each project directory (`uv run ...`, `uv add ...`), not `pip` or raw `python`.

#### GCP migration checkpoints (current architecture)

- Queueing/orchestration uses **Pub/Sub + Cloud Run services** (not SQS/Lambda runtime coupling).
- Operational database is **PostgreSQL via `DATABASE_URL`** (Cloud SQL-compatible).
- API runtime is **FastAPI on Cloud Run** with endpoint health check at `/health`.
- Frontend is static hosting in **GCS bucket**, calling API via `NEXT_PUBLIC_API_URL`.

#### Frontend ↔ Backend connection checklist (GCP only)

- Set `cors_origins` in `terraform/7_frontend/terraform.tfvars` to include both local dev origin and deployed frontend origin.
- Deploy `terraform/7_frontend`, then build frontend with `NEXT_PUBLIC_API_URL` set to Terraform output `api_url`.
- Upload `frontend/out` to the GCS bucket from Terraform output `frontend_bucket`.
- Run `uv run scripts/verify_frontend_backend.py --api-url <api_url> --origin <frontend_origin>` to validate `/health` and CORS preflight.

#### If your PR shows merge conflicts on GCP migration files

- Run `uv run scripts/resolve_gcp_merge_conflicts.py --strategy ours` to auto-resolve the known conflict set from the GCP migration branch.
- Then review staged changes with `git diff --staged` and commit.
