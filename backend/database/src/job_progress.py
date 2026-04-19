"""Helpers for staged analysis progress tracking."""

from __future__ import annotations

from datetime import datetime
from typing import Any

STAGE_CONFIG: dict[str, dict[str, Any]] = {
    "queued": {
        "percent": 5,
        "message": "Analysis request queued for the Financial Planner.",
        "active_agents": ["Financial Planner"],
    },
    "planner_started": {
        "percent": 12,
        "message": "Financial Planner has started orchestration.",
        "active_agents": ["Financial Planner"],
    },
    "tagging_instruments": {
        "percent": 22,
        "message": "Checking and classifying portfolio instruments.",
        "active_agents": ["Financial Planner"],
    },
    "refreshing_market_data": {
        "percent": 34,
        "message": "Refreshing delayed market prices from Polygon.",
        "active_agents": ["Financial Planner"],
    },
    "preparing_portfolio_context": {
        "percent": 46,
        "message": "Preparing portfolio context for the specialist agents.",
        "active_agents": ["Financial Planner"],
    },
    "running_reporter": {
        "percent": 56,
        "message": "Generating the portfolio report.",
        "active_agents": ["Portfolio Analyst"],
    },
    "running_charter": {
        "percent": 68,
        "message": "Building portfolio charts.",
        "active_agents": ["Chart Specialist"],
    },
    "running_retirement": {
        "percent": 80,
        "message": "Calculating retirement projections.",
        "active_agents": ["Retirement Planner"],
    },
    "finalizing": {
        "percent": 96,
        "message": "Finalizing analysis results.",
        "active_agents": ["Financial Planner"],
    },
    "completed": {
        "percent": 100,
        "message": "Analysis complete.",
        "active_agents": [],
    },
    "failed": {
        "percent": 100,
        "message": "Analysis failed.",
        "active_agents": [],
    },
}

PAYLOAD_STAGE_ORDER = (
    ("report_payload", 70, "Portfolio report complete."),
    ("charts_payload", 82, "Portfolio charts complete."),
    ("retirement_payload", 94, "Retirement analysis complete."),
)


def utc_now_iso() -> str:
    return datetime.utcnow().isoformat()


def mark_job_progress(
    db,
    job_id: str,
    stage_key: str,
    *,
    message: str | None = None,
    active_agents: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> int:
    """Persist a stage checkpoint into the job summary payload."""
    stage = STAGE_CONFIG.get(stage_key, {})
    progress_payload = {
        "progress": {
            "stage_key": stage_key,
            "message": message or stage.get("message", "Analysis update."),
            "active_agents": active_agents if active_agents is not None else stage.get("active_agents", []),
            "updated_at": utc_now_iso(),
        },
        "progress_state": {
            stage_key: {
                "completed_at": utc_now_iso(),
            }
        },
    }

    if metadata:
        progress_payload["progress"]["metadata"] = metadata

    return db.jobs.merge_summary(job_id, progress_payload)


def derive_job_progress(job: dict[str, Any]) -> dict[str, Any]:
    """Derive a user-facing progress object from job state and payloads."""
    summary_payload = job.get("summary_payload") or {}
    stored_progress = summary_payload.get("progress") or {}
    stage_key = stored_progress.get("stage_key") or "queued"

    if job.get("status") == "completed":
        stage_key = "completed"
    elif job.get("status") == "failed":
        stage_key = "failed"

    stage = STAGE_CONFIG.get(stage_key, STAGE_CONFIG["queued"])
    percent = int(stage["percent"])
    message = stored_progress.get("message") or stage["message"]
    active_agents = list(stored_progress.get("active_agents") or stage["active_agents"])

    completed_payload_count = 0
    for payload_name, payload_percent, payload_message in PAYLOAD_STAGE_ORDER:
        if job.get(payload_name):
            completed_payload_count += 1
            percent = max(percent, payload_percent)
            message = payload_message

    if job.get("status") == "running":
        if completed_payload_count < len(PAYLOAD_STAGE_ORDER) and stage_key in {
            "running_reporter",
            "running_charter",
            "running_retirement",
            "finalizing",
        }:
            remaining_agents = []
            if not job.get("report_payload"):
                remaining_agents.append("Portfolio Analyst")
            if not job.get("charts_payload"):
                remaining_agents.append("Chart Specialist")
            if not job.get("retirement_payload"):
                remaining_agents.append("Retirement Planner")
            active_agents = remaining_agents
            if completed_payload_count:
                message = f"{completed_payload_count} of 3 specialist stages completed."

    if job.get("status") == "failed" and job.get("error_message"):
        message = job["error_message"]

    return {
        "percent": percent,
        "stage_key": stage_key,
        "message": message,
        "active_agents": active_agents,
        "updated_at": stored_progress.get("updated_at"),
        "payloads_completed": {
            "report": bool(job.get("report_payload")),
            "charts": bool(job.get("charts_payload")),
            "retirement": bool(job.get("retirement_payload")),
        },
    }
