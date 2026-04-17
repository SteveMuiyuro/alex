#!/usr/bin/env python3
"""
Deploy helper for GCP-based Alex frontend/API.

This script intentionally avoids provider-specific packaging logic and focuses on
high-level deployment orchestration:
1. Build frontend
2. Apply Terraform for frontend module
3. Print next-step commands for uploading static assets and verifying API
"""

from pathlib import Path
import subprocess
import os


def run(cmd: list[str], cwd: Path) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def get_output(name: str, cwd: Path) -> str:
    result = subprocess.run(
        ["terraform", "output", "-raw", name],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    frontend_dir = root / "frontend"
    tf_dir = root / "terraform" / "7_frontend"

    print("🚀 Deploy helper (GCP)")

    run(["terraform", "init"], tf_dir)
    run(["terraform", "apply"], tf_dir)
    api_url = get_output("api_url", tf_dir)
    frontend_bucket = get_output("frontend_bucket", tf_dir)

    build_env = os.environ.copy()
    build_env["NEXT_PUBLIC_API_URL"] = api_url
    print(f"$ NEXT_PUBLIC_API_URL={api_url} npm run build")
    subprocess.run(["npm", "run", "build"], cwd=frontend_dir, check=True, env=build_env)

    print("\n✅ Terraform apply completed.")
    print("Next steps:")
    print(f"1) Upload frontend build output to GCS: gsutil -m rsync -r frontend/out gs://{frontend_bucket}")
    print(f"2) API URL wired into build: {api_url}")
    print(f"3) Verify API health: curl {api_url}/health")
    print("4) Open frontend and sign in, then verify /api/user, /api/accounts, /api/jobs requests in browser devtools.")


if __name__ == "__main__":
    main()
