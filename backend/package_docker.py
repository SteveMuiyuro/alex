#!/usr/bin/env python3
"""
Build helper for agent container images.

This script checks whether each agent directory has a Dockerfile and prints
build commands for Cloud Run deployment.
"""

import sys
from pathlib import Path


def main() -> int:
    backend_dir = Path(__file__).parent
    agents = ["tagger", "reporter", "charter", "retirement", "planner"]

    print("=" * 60)
    print("AGENT IMAGE BUILD CHECK")
    print("=" * 60)

    missing = []
    for agent in agents:
        dockerfile = backend_dir / agent / "Dockerfile"
        if dockerfile.exists():
            print(f"✅ {agent}: Dockerfile found")
        else:
            print(f"⚠️  {agent}: Dockerfile missing")
            missing.append(agent)

    print("\nSuggested build command pattern:")
    print("  gcloud builds submit --tag <REGION>-docker.pkg.dev/<PROJECT>/<REPO>/<AGENT>:latest backend/<AGENT>")

    if missing:
        print(f"\nMissing Dockerfile for: {', '.join(missing)}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
