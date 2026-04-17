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


def run(cmd: list[str], cwd: Path) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    frontend_dir = root / "frontend"
    tf_dir = root / "terraform" / "7_frontend"

    print("🚀 Deploy helper (GCP)")

    run(["npm", "run", "build"], frontend_dir)
    run(["terraform", "init"], tf_dir)
    run(["terraform", "apply"], tf_dir)

    print("\n✅ Terraform apply completed.")
    print("Next steps:")
    print("1) Upload frontend build output to your configured GCS bucket.")
    print("2) Confirm API service URL from Terraform outputs.")
    print("3) Verify /api/health and frontend /dashboard.")


if __name__ == "__main__":
    main()
