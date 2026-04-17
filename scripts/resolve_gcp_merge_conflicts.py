#!/usr/bin/env python3
"""
Resolve common merge conflicts for the GCP migration files.

Run this only when git is in a conflicted merge state.

Example:
  uv run scripts/resolve_gcp_merge_conflicts.py --strategy ours
"""

from __future__ import annotations

import argparse
import subprocess
import sys


CONFLICT_FILES = [
    "README.md",
    "backend/planner/agent.py",
    "backend/planner/lambda_handler.py",
    "frontend/lib/api.ts",
    "scripts/deploy.py",
    "terraform/7_frontend/main.tf",
    "terraform/7_frontend/terraform.tfvars.example",
    "terraform/7_frontend/variables.tf",
]


def run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--strategy",
        choices=["ours", "theirs"],
        default="ours",
        help="Conflict strategy to apply for known files.",
    )
    args = parser.parse_args()

    unmerged = run(["git", "diff", "--name-only", "--diff-filter=U"]).splitlines()
    if not unmerged:
        print("No unmerged files detected.")
        return 0

    conflict_set = set(unmerged)
    handled = []

    for file_path in CONFLICT_FILES:
        if file_path in conflict_set:
            subprocess.run(["git", "checkout", f"--{args.strategy}", file_path], check=True)
            subprocess.run(["git", "add", file_path], check=True)
            handled.append(file_path)

    print(f"Handled {len(handled)} known conflict file(s) with --{args.strategy}:")
    for file_path in handled:
        print(f"  - {file_path}")

    remaining = run(["git", "diff", "--name-only", "--diff-filter=U"]).splitlines()
    if remaining:
        print("\nStill unresolved (manual review required):")
        for file_path in remaining:
            print(f"  - {file_path}")
        return 1

    print("\nAll merge conflicts are resolved and staged.")
    print("Next: review `git diff --staged`, then commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
