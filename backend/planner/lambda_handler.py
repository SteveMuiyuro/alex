"""
Financial Planner Orchestrator runtime handler.
"""

import os
import json
import asyncio
import base64
import logging
import base64
from typing import Dict, Any

from agents import Agent, Runner, trace
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from litellm.exceptions import RateLimitError
from fastapi import FastAPI, HTTPException

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

# Import database package
from src import Database

from templates import ORCHESTRATOR_INSTRUCTIONS
from agent import create_agent, handle_missing_instruments, load_portfolio_summary
from market import update_instrument_prices
from observability import observe

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize database
db = Database()

# Cloud Run API for health and Pub/Sub push handling
app = FastAPI(title="Alex Planner Service", version="1.0.0")

@retry(
    retry=retry_if_exception_type(RateLimitError),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    before_sleep=lambda retry_state: logger.info(f"Planner: Rate limit hit, retrying in {retry_state.next_action.sleep} seconds...")
)
async def run_orchestrator(job_id: str) -> None:
    """Run the orchestrator agent to coordinate portfolio analysis."""
    try:
        # Update job status to running
        db.jobs.update_status(job_id, 'running')
        
        # Handle missing instruments first (non-agent pre-processing)
        await asyncio.to_thread(handle_missing_instruments, job_id, db)

        # Update instrument prices after tagging
        logger.info("Planner: Updating instrument prices from market data")
        await asyncio.to_thread(update_instrument_prices, job_id, db)

        # Load portfolio summary (just statistics, not full data)
        portfolio_summary = await asyncio.to_thread(load_portfolio_summary, job_id, db)
        
        # Create agent with tools and context
        model, tools, task, context = create_agent(job_id, portfolio_summary, db)
        
        # Run the orchestrator
        with trace("Planner Orchestrator"):
            from agent import PlannerContext
            agent = Agent[PlannerContext](
                name="Financial Planner",
                instructions=ORCHESTRATOR_INSTRUCTIONS,
                model=model,
                tools=tools
            )
            
            result = await Runner.run(
                agent,
                input=task,
                context=context,
                max_turns=20
            )
            
            # Mark job as completed after all agents finish
            db.jobs.update_status(job_id, "completed")
            logger.info(f"Planner: Job {job_id} completed successfully")
            
    except Exception as e:
        logger.error(f"Planner: Error in orchestration: {e}", exc_info=True)
        db.jobs.update_status(job_id, 'failed', error_message=str(e))
        raise

def lambda_handler(event, context):
    """
    Runtime handler for queue-triggered orchestration.

    Expected event from Pub/Sub push or generic queue adapters:
    {
        "records": [
            {
                "body": "job_id"
            }
        ]
    }
    """
    # Wrap entire handler with observability context
    with observe():
        try:
            logger.info(f"Planner runtime invoked with event: {json.dumps(event)[:500]}")

            # Extract job_id from queue message formats
            if 'Records' in event and len(event['Records']) > 0:
                job_id = event['Records'][0]['body']
                if isinstance(job_id, str) and job_id.startswith('{'):
                    # Body might be JSON
                    try:
                        body = json.loads(job_id)
                        job_id = body.get('job_id', job_id)
                    except json.JSONDecodeError:
                        pass
            elif 'message' in event and isinstance(event['message'], dict):
                data = event['message'].get('data')
                if data:
                    decoded_json = base64.b64decode(data).decode("utf-8")
                    decoded = json.loads(decoded_json)
                    job_id = decoded.get('job_id')
                else:
                    job_id = event['message'].get('job_id')
            elif 'job_id' in event:
                # Direct invocation
                job_id = event['job_id']
            else:
                logger.error("No job_id found in event")
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'No job_id provided'})
                }

            logger.info(f"Planner: Starting orchestration for job {job_id}")

            # Run the orchestrator
            asyncio.run(run_orchestrator(job_id))

            return {
                'statusCode': 200,
                'body': json.dumps({
                    'success': True,
                    'message': f'Analysis completed for job {job_id}'
                })
            }

        except Exception as e:
            logger.error(f"Planner: Error in lambda handler: {e}", exc_info=True)
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'success': False,
                    'error': str(e)
                })
            }


def _decode_pubsub_push(envelope: Dict[str, Any]) -> Dict[str, Any]:
    """Decode a Pub/Sub push envelope payload into JSON message dict."""
    message = envelope.get("message", {})
    data = message.get("data")
    if not data:
        raise ValueError("Pub/Sub push message missing data")

    decoded_bytes = base64.b64decode(data)
    decoded = decoded_bytes.decode("utf-8")
    parsed = json.loads(decoded)
    if not isinstance(parsed, dict):
        raise ValueError("Pub/Sub message payload must be a JSON object")
    return parsed


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/pubsub/push")
async def pubsub_push_handler(envelope: Dict[str, Any]):
    """
    Handle Pub/Sub push messages from alex-planner-sub.
    Expects standard Pub/Sub push envelope with base64-encoded JSON payload.
    """
    try:
        payload = _decode_pubsub_push(envelope)
        result = lambda_handler(payload, None)
        if result.get("statusCode", 500) >= 400:
            raise HTTPException(status_code=500, detail=result.get("body", "Planner failed"))
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Planner push handler failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/run")
async def run_handler(payload: Dict[str, Any]):
    """Direct HTTP trigger for planner; useful for smoke tests."""
    result = lambda_handler(payload, None)
    status_code = result.get("statusCode", 500)
    body = result.get("body")
    parsed_body = json.loads(body) if isinstance(body, str) else body
    if status_code >= 400:
        raise HTTPException(status_code=status_code, detail=parsed_body)
    return parsed_body

# For local testing
if __name__ == "__main__":
    if os.getenv("RUN_PLANNER_HTTP", "false").lower() == "true":
        import uvicorn

        uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
        raise SystemExit(0)

    # Define a test user
    test_user_id = "test_user_planner_local"

    # Ensure the test user exists before creating a job
    from src.schemas import UserCreate, JobCreate
    
    user = db.users.find_by_clerk_id(test_user_id)
    if not user:
        print(f"Creating test user: {test_user_id}")
        user_create = UserCreate(clerk_user_id=test_user_id, display_name="Test Planner User")
        db.users.create(user_create.model_dump(), returning='clerk_user_id')

    # Create a test job
    print("Creating test job...")
    job_create = JobCreate(
        clerk_user_id=test_user_id,
        job_type='portfolio_analysis',
        request_payload={
            'analysis_type': 'comprehensive',
            'test': True
        }
    )
    
    job = db.jobs.create(job_create.model_dump())
    job_id = job
    
    print(f"Created test job: {job_id}")
    
    # Test the handler
    test_event = {
        'job_id': job_id
    }
    
    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))
