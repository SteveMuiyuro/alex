#!/usr/bin/env python3
"""
Build helper for agent container images.

This script checks whether each service directory has a Dockerfile and prints
build commands for Cloud Run deployment.
"""

import sys
from pathlib import Path


def main() -> int:
    backend_dir = Path(__file__).parent
    services = ["api", "tagger", "reporter", "charter", "retirement", "planner", "researcher"]

    print("=" * 60)
    print("AGENT IMAGE BUILD CHECK")
    print("=" * 60)

    missing = []
    for service in services:
        dockerfile = backend_dir / service / "Dockerfile"
        if dockerfile.exists():
            print(f"✅ {service}: Dockerfile found")
        else:
            print(f"⚠️  {service}: Dockerfile missing")
            missing.append(service)

    print("\nSuggested build command pattern:")
    print("  gcloud builds submit --tag <REGION>-docker.pkg.dev/<PROJECT>/<REPO>/<SERVICE>:latest --file backend/<SERVICE>/Dockerfile .")

    if missing:
        print(f"\nMissing Dockerfile for: {', '.join(missing)}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
