#!/usr/bin/env python3
"""
Destroy helper for GCP Terraform modules.
"""

from pathlib import Path
import subprocess


MODULES = [
    "8_enterprise",
    "7_frontend",
    "6_agents",
    "5_database",
    "4_researcher",
    "3_ingestion",
    "2_sagemaker",
]


def run(cmd: list[str], cwd: Path) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    tf_root = root / "terraform"

    print("🧹 Destroy helper (GCP)")
    for module in MODULES:
        module_dir = tf_root / module
        if module_dir.exists():
            print(f"\nDestroying terraform/{module} ...")
            run(["terraform", "destroy"], module_dir)


if __name__ == "__main__":
    main()
