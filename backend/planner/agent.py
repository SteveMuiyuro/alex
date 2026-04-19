"""
Financial Planner Orchestrator Agent - coordinates portfolio analysis across specialized agents.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass
import httpx

from agents import function_span, function_tool, RunContextWrapper
from agents.extensions.models.litellm_model import LitellmModel
from src.openai_tracing import dump_trace_json, get_workflow_observer

logger = logging.getLogger()

# Agent service endpoints (Cloud Run)
TAGGER_ENDPOINT = os.getenv("TAGGER_ENDPOINT", "http://localhost:8001/tag")
REPORTER_ENDPOINT = os.getenv("REPORTER_ENDPOINT", "http://localhost:8002/report")
CHARTER_ENDPOINT = os.getenv("CHARTER_ENDPOINT", "http://localhost:8003/chart")
RETIREMENT_ENDPOINT = os.getenv("RETIREMENT_ENDPOINT", "http://localhost:8004/retirement")
MOCK_LAMBDAS = os.getenv("MOCK_LAMBDAS", "false").lower() == "true"


@dataclass
class PlannerContext:
    """Context for planner agent tools."""
    job_id: str


async def invoke_lambda_agent(
    agent_name: str, endpoint: str, payload: Dict[str, Any]
) -> Dict[str, Any]:
    """Invoke another agent service endpoint."""

    # For local testing with mocked agents
    if MOCK_LAMBDAS:
        logger.info(f"[MOCK] Would invoke {agent_name} with payload: {json.dumps(payload)[:200]}")
        return {"success": True, "message": f"[Mock] {agent_name} completed", "mock": True}

    span_input = {"agent_name": agent_name, "endpoint": endpoint, "payload": payload}
    workflow_observer = get_workflow_observer()
    with workflow_observer.start_as_current_span(
        name=f"workflow_invoke_{agent_name.lower()}",
        input=span_input,
        metadata={"service": "planner", "target_agent": agent_name},
    ) as workflow_span:
        job_id = payload.get("job_id")
        if job_id:
            workflow_span.update_trace(session_id=str(job_id))

        with function_span(name=f"invoke_{agent_name.lower()}", input=dump_trace_json(span_input)) as span:
            try:
                logger.info(f"Invoking {agent_name} service: {endpoint}")
                async with httpx.AsyncClient(timeout=120) as client:
                    response = await client.post(endpoint, json=payload)
                    response.raise_for_status()
                    result = response.json()

                span.span_data.output = dump_trace_json(result)
                workflow_span.update(output=result)
                logger.info(f"{agent_name} completed successfully")
                return result

            except Exception as e:
                error_payload = {"type": type(e).__name__, "message": str(e)}
                span.span_data.output = dump_trace_json({"error": error_payload})
                span.set_error(str(e))
                workflow_span.update(status_message=str(e), output={"error": error_payload})
                logger.error(f"Error invoking {agent_name}: {e}")
                return {"error": str(e)}


def handle_missing_instruments(job_id: str, db) -> None:
    """
    Check for and tag any instruments missing allocation data.
    This is done automatically before the agent runs.
    """
    workflow_observer = get_workflow_observer()
    logger.info("Planner: Checking for instruments missing allocation data...")

    # Get job and portfolio data
    job = db.jobs.find_by_id(job_id)
    if not job:
        logger.error(f"Job {job_id} not found")
        return

    user_id = job["clerk_user_id"]
    accounts = db.accounts.find_by_user(user_id)

    missing = []
    for account in accounts:
        positions = db.positions.find_by_account(account["id"])
        for position in positions:
            instrument = db.instruments.find_by_symbol(position["symbol"])
            if instrument:
                has_allocations = bool(
                    instrument.get("allocation_regions")
                    and instrument.get("allocation_sectors")
                    and instrument.get("allocation_asset_class")
                )
                if not has_allocations:
                    missing.append(
                        {"symbol": position["symbol"], "name": instrument.get("name", "")}
                    )
            else:
                missing.append({"symbol": position["symbol"], "name": ""})

    if missing:
        logger.info(
            f"Planner: Found {len(missing)} instruments needing classification: {[m['symbol'] for m in missing]}"
        )

        try:
            payload = {"job_id": job_id, "instruments": missing}
            with workflow_observer.start_as_current_span(
                name="workflow_invoke_tagger_preprocessing",
                input=payload,
                metadata={"service": "planner", "target_agent": "tagger", "reason": "missing_instruments"},
            ) as workflow_span:
                workflow_span.update_trace(session_id=str(job_id))
                with function_span(name="invoke_tagger", input=dump_trace_json(payload)) as span:
                    with httpx.Client(timeout=120) as client:
                        response = client.post(TAGGER_ENDPOINT, json=payload)
                        response.raise_for_status()
                        result = {"status_code": response.status_code, "tagged_symbols": [item["symbol"] for item in missing]}
                        span.span_data.output = dump_trace_json(result)
                        workflow_span.update(output=result)
            logger.info(
                f"Planner: InstrumentTagger completed - Tagged {len(missing)} instruments"
            )

        except Exception as e:
            with workflow_observer.start_as_current_span(
                name="workflow_invoke_tagger_preprocessing_error",
                input={"job_id": job_id, "error": str(e)},
                metadata={"service": "planner", "target_agent": "tagger"},
            ) as workflow_span:
                workflow_span.update_trace(session_id=str(job_id))
                workflow_span.update(status_message=str(e), output={"error": str(e)})
            logger.error(f"Planner: Error tagging instruments: {e}")
    else:
        logger.info("Planner: All instruments have allocation data")


def load_portfolio_summary(job_id: str, db) -> Dict[str, Any]:
    """Load basic portfolio summary statistics only."""
    try:
        job = db.jobs.find_by_id(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        user_id = job["clerk_user_id"]
        user = db.users.find_by_clerk_id(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        accounts = db.accounts.find_by_user(user_id)
        
        # Calculate simple summary statistics
        total_value = 0.0
        total_positions = 0
        total_cash = 0.0
        
        for account in accounts:
            total_cash += float(account.get("cash_balance", 0))
            positions = db.positions.find_by_account(account["id"])
            total_positions += len(positions)
            
            # Add position values
            for position in positions:
                instrument = db.instruments.find_by_symbol(position["symbol"])
                if instrument and instrument.get("current_price"):
                    price = float(instrument["current_price"])
                    quantity = float(position["quantity"])
                    total_value += price * quantity
        
        total_value += total_cash
        
        # Return only summary statistics
        return {
            "total_value": total_value,
            "num_accounts": len(accounts),
            "num_positions": total_positions,
            "years_until_retirement": user.get("years_until_retirement", 30),
            "target_retirement_income": float(user.get("target_retirement_income", 80000))
        }

    except Exception as e:
        logger.error(f"Error loading portfolio summary: {e}")
        raise


async def invoke_reporter_internal(job_id: str) -> str:
    """
    Invoke the Report Writer Lambda to generate portfolio analysis narrative.

    Args:
        job_id: The job ID for the analysis

    Returns:
        Confirmation message
    """
    result = await invoke_lambda_agent("Reporter", REPORTER_ENDPOINT, {"job_id": job_id})

    if "error" in result:
        raise RuntimeError(f"Reporter agent failed: {result['error']}")

    return "Reporter agent completed successfully. Portfolio analysis narrative has been generated and saved."


async def invoke_charter_internal(job_id: str) -> str:
    """
    Invoke the Chart Maker Lambda to create portfolio visualizations.

    Args:
        job_id: The job ID for the analysis

    Returns:
        Confirmation message
    """
    result = await invoke_lambda_agent(
        "Charter", CHARTER_ENDPOINT, {"job_id": job_id}
    )

    if "error" in result:
        raise RuntimeError(f"Charter agent failed: {result['error']}")

    return "Charter agent completed successfully. Portfolio visualizations have been created and saved."


async def invoke_retirement_internal(job_id: str) -> str:
    """
    Invoke the Retirement Specialist Lambda for retirement projections.

    Args:
        job_id: The job ID for the analysis

    Returns:
        Confirmation message
    """
    result = await invoke_lambda_agent("Retirement", RETIREMENT_ENDPOINT, {"job_id": job_id})

    if "error" in result:
        raise RuntimeError(f"Retirement agent failed: {result['error']}")

    return "Retirement agent completed successfully. Retirement projections have been calculated and saved."



@function_tool
async def invoke_reporter(wrapper: RunContextWrapper[PlannerContext]) -> str:
    """Invoke the Report Writer agent to generate portfolio analysis narrative."""
    return await invoke_reporter_internal(wrapper.context.job_id)

@function_tool
async def invoke_charter(wrapper: RunContextWrapper[PlannerContext]) -> str:
    """Invoke the Chart Maker agent to create portfolio visualizations."""
    return await invoke_charter_internal(wrapper.context.job_id)

@function_tool
async def invoke_retirement(wrapper: RunContextWrapper[PlannerContext]) -> str:
    """Invoke the Retirement Specialist agent for retirement projections."""
    return await invoke_retirement_internal(wrapper.context.job_id)


def create_agent(job_id: str, portfolio_summary: Dict[str, Any], db):
    """Create the orchestrator agent with tools."""
    
    # Create context for tools
    context = PlannerContext(job_id=job_id)

    # Get model configuration
    model_id = os.getenv("VERTEX_MODEL", "gemini-2.5-flash")
    model = LitellmModel(model=f"vertex_ai/{model_id}")

    tools = [
        invoke_reporter,
        invoke_charter,
        invoke_retirement,
    ]

    # Create minimal task context
    task = f"""Job {job_id} has {portfolio_summary['num_positions']} positions.
Retirement: {portfolio_summary['years_until_retirement']} years.

Call the appropriate agents."""

    return model, tools, task, context
