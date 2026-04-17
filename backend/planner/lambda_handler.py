"""
Financial Planner Orchestrator runtime handler.
"""

import os
import json
import asyncio
import logging
import base64
from typing import Dict, Any

from agents import Agent, Runner, trace
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from litellm.exceptions import RateLimitError

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

def _extract_job_id_from_event(event: Dict[str, Any]) -> str | None:
    """Extract job_id from supported queue event formats (GCP and legacy AWS)."""
    # AWS SQS format (legacy compatibility)
    if "Records" in event and len(event["Records"]) > 0:
        body = event["Records"][0].get("body")
        if isinstance(body, str) and body.startswith("{"):
            try:
                payload = json.loads(body)
                return payload.get("job_id")
            except json.JSONDecodeError:
                return body
        return body

    # Pub/Sub push format:
    # {"message": {"data": "base64-encoded-json-or-string"}}
    if "message" in event and isinstance(event["message"], dict):
        message = event["message"]
        data = message.get("data")
        if data:
            try:
                decoded_data = base64.b64decode(data).decode("utf-8")
                if decoded_data.startswith("{"):
                    return json.loads(decoded_data).get("job_id")
                return decoded_data
            except Exception:
                logger.warning("Planner: Failed to decode Pub/Sub message.data", exc_info=True)
        return message.get("job_id")

    # Direct invocation format (local/dev)
    if "job_id" in event:
        return event["job_id"]

    return None


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

            # Extract job_id from supported queue formats
            job_id = _extract_job_id_from_event(event)
            if not job_id:
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


def cloud_function_entry(event, context):
    """
    Google Cloud Functions / Eventarc entrypoint wrapper.

    This accepts the standard Pub/Sub event payload and routes it through the
    shared queue handler so local and cloud execution stay consistent.
    """
    return lambda_handler(event, context)

# For local testing
if __name__ == "__main__":
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
