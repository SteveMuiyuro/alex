"""
Live smoke test for the deployed GCP backend.

Creates a synthetic user, account, instrument, position, and job in Cloud SQL,
invokes the deployed planner Cloud Run endpoint with a Pub/Sub-style payload,
then polls the job row for completion and payload updates.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import time
from decimal import Decimal
from uuid import uuid4

import httpx

from src import Database


PLANNER_URL = os.getenv("PLANNER_URL", "https://alex-planner-kwbyvqojoa-uc.a.run.app")
TAGGER_URL = os.getenv("TAGGER_URL", "https://alex-tagger-kwbyvqojoa-uc.a.run.app")


def ensure_test_data(db: Database) -> tuple[str, str]:
    test_suffix = uuid4().hex[:8]
    clerk_user_id = f"smoke_test_{test_suffix}"
    symbol = f"SMK{test_suffix[:4].upper()}"

    db.users.create_user(
        clerk_user_id=clerk_user_id,
        display_name="Backend Smoke Test",
        years_until_retirement=25,
        target_retirement_income=Decimal("85000"),
    )

    # Insert a synthetic instrument with complete allocations and price data.
    db.client.insert(
        "instruments",
        {
            "symbol": symbol,
            "name": f"Smoke Test Equity {test_suffix}",
            "instrument_type": "stock",
            "current_price": Decimal("125.50"),
            "allocation_regions": {"north_america": 100},
            "allocation_sectors": {"technology": 100},
            "allocation_asset_class": {"equity": 100},
        },
        returning="symbol",
    )

    account_id = db.accounts.create_account(
        clerk_user_id=clerk_user_id,
        account_name=f"Smoke Brokerage {test_suffix}",
        account_purpose="Backend smoke test",
        cash_balance=Decimal("2500"),
        cash_interest=Decimal("0.01"),
    )

    db.positions.add_position(account_id, symbol, Decimal("10"))

    job_id = db.jobs.create_job(
        clerk_user_id=clerk_user_id,
        job_type="portfolio_analysis",
        request_payload={"analysis_type": "comprehensive", "test": True},
    )

    return job_id, symbol


async def invoke_tagger(symbol: str) -> dict:
    payload = {
        "instruments": [
            {"symbol": symbol, "name": "Apple Inc."},
        ]
    }
    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(f"{TAGGER_URL}/tag", json=payload)
        return {
            "status_code": response.status_code,
            "body": response.json(),
        }


async def invoke_planner(job_id: str) -> dict:
    message = {"job_id": job_id}
    payload = {
        "message": {
            "data": base64.b64encode(json.dumps(message).encode("utf-8")).decode("utf-8")
        }
    }
    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(f"{PLANNER_URL}/pubsub/push", json=payload)
        return {
            "status_code": response.status_code,
            "body": response.json(),
        }


def poll_job(db: Database, job_id: str, timeout_seconds: int = 300) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        job = db.jobs.find_by_id(job_id)
        if not job:
            raise RuntimeError(f"Job {job_id} disappeared")

        status = job.get("status")
        if status in {"completed", "failed"}:
            return job

        time.sleep(5)

    raise TimeoutError(f"Job {job_id} did not finish within {timeout_seconds} seconds")


async def main() -> None:
    db = Database()

    job_id, symbol = ensure_test_data(db)
    print(json.dumps({"created_job_id": job_id, "seed_symbol": symbol}, indent=2))

    tagger_result = await invoke_tagger("AAPL")
    print(json.dumps({"tagger_result": tagger_result}, indent=2))

    planner_result = await invoke_planner(job_id)
    print(json.dumps({"planner_result": planner_result}, indent=2))

    final_job = poll_job(db, job_id)
    summary = {
        "job_id": job_id,
        "status": final_job.get("status"),
        "error_message": final_job.get("error_message"),
        "has_report_payload": bool(final_job.get("report_payload")),
        "has_charts_payload": bool(final_job.get("charts_payload")),
        "has_retirement_payload": bool(final_job.get("retirement_payload")),
        "has_summary_payload": bool(final_job.get("summary_payload")),
    }
    print(json.dumps({"final_job": summary}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
