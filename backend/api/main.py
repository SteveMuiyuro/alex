"""
FastAPI backend for Alex Financial Advisor
Handles all API routes with Clerk JWT authentication
"""

import os
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from time import monotonic
import uuid

import httpx
from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError
from dotenv import load_dotenv
from fastapi_clerk_auth import ClerkConfig, ClerkHTTPBearer, HTTPAuthorizationCredentials
from google.cloud import pubsub_v1

from src import Database
from src.job_progress import derive_job_progress, mark_job_progress
from src.openai_tracing import observe
from src.schemas import (
    UserCreate,
    AccountCreate,
    PositionCreate,
    JobCreate, JobUpdate,
    JobType, JobStatus
)

# Load environment variables
load_dotenv(override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Alex Financial Advisor API",
    description="Backend API for AI-powered financial planning",
    version="1.0.0"
)

# ✅ UPDATED CORS CONFIGURATION (GCP READY)
cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,https://storage.googleapis.com"
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom exception handlers
@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid input data. Please check your request and try again."}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    user_friendly_messages = {
        401: "Your session has expired. Please sign in again.",
        403: "You don't have permission to access this resource.",
        404: "The requested resource was not found.",
        429: "Too many requests. Please slow down and try again later.",
        500: "An internal error occurred. Please try again later.",
        503: "The service is temporarily unavailable. Please try again later."
    }

    message = user_friendly_messages.get(exc.status_code, exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": message}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Our team has been notified."}
    )

# Initialize services
db = Database()

# Pub/Sub
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
PUBSUB_TOPIC = os.getenv("PUBSUB_TOPIC", "")
pubsub_publisher = pubsub_v1.PublisherClient() if PUBSUB_TOPIC else None
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY", "")
POLYGON_PLAN = os.getenv("POLYGON_PLAN", "free")
POLYGON_BASE_URL = "https://api.polygon.io"
# Keep the symbol set small enough for the free-plan request budget while still
# giving a useful cross-section of major market benchmarks and leaders.
MARKET_SNAPSHOT_SYMBOLS = ["SPY", "QQQ", "DIA", "AAPL", "MSFT", "NVDA"]
MARKET_CACHE_TTL_SECONDS = 300
market_snapshot_cache: dict[str, Any] = {"expires_at": 0.0, "payload": None}


def get_pubsub_topic_path() -> str:
    if not PUBSUB_TOPIC:
        return ""
    if PUBSUB_TOPIC.startswith("projects/"):
        return PUBSUB_TOPIC
    if GOOGLE_CLOUD_PROJECT:
        return pubsub_publisher.topic_path(GOOGLE_CLOUD_PROJECT, PUBSUB_TOPIC)
    return PUBSUB_TOPIC


async def fetch_polygon_market_snapshot() -> dict[str, Any]:
    """Fetch a delayed market snapshot suitable for dashboard display."""
    if not POLYGON_API_KEY:
        return {
            "quotes": [],
            "news": [],
            "delayed": True,
            "source": "polygon",
            "plan": POLYGON_PLAN,
            "as_of": None,
            "unavailable_reason": "POLYGON_API_KEY is not configured",
        }

    if market_snapshot_cache["payload"] and market_snapshot_cache["expires_at"] > monotonic():
        return market_snapshot_cache["payload"]

    quotes: list[dict[str, Any]] = []
    news: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=20) as client:
        for symbol in MARKET_SNAPSHOT_SYMBOLS:
            try:
                prev_response = await client.get(
                    f"{POLYGON_BASE_URL}/v2/aggs/ticker/{symbol}/prev",
                    params={"adjusted": "true", "apiKey": POLYGON_API_KEY},
                )
                prev_response.raise_for_status()
                prev_payload = prev_response.json()
                results = prev_payload.get("results") or []
                if not results:
                    logger.info("Polygon previous-day data returned no rows for %s", symbol)
                    continue

                bar = results[0]
                open_price = bar.get("o")
                close_price = bar.get("c")
                if open_price in (None, 0) or close_price is None:
                    continue

                change = float(close_price) - float(open_price)
                change_percent = (change / float(open_price)) * 100 if open_price else 0.0
                quotes.append(
                    {
                        "symbol": symbol,
                        "price": round(float(close_price), 2),
                        "change": round(change, 2),
                        "change_percent": round(change_percent, 2),
                        "updated_at": bar.get("t"),
                    }
                )
            except Exception as exc:
                logger.info("Polygon previous-day quote unavailable for %s: %s", symbol, exc)

        try:
            news_response = await client.get(
                f"{POLYGON_BASE_URL}/v2/reference/news",
                params={
                    "limit": 4,
                    "order": "desc",
                    "sort": "published_utc",
                    "apiKey": POLYGON_API_KEY,
                },
            )
            news_response.raise_for_status()
            news_payload = news_response.json()
            for item in news_payload.get("results", []):
                news.append(
                    {
                        "id": item.get("id"),
                        "title": item.get("title"),
                        "publisher": (item.get("publisher") or {}).get("name"),
                        "published_utc": item.get("published_utc"),
                        "article_url": item.get("article_url"),
                        "tickers": item.get("tickers", []),
                    }
                )
        except Exception as exc:
            logger.info("Polygon news unavailable for current plan or request: %s", exc)

    payload = {
        "quotes": quotes,
        "news": news,
        "delayed": True,
        "source": "polygon",
        "plan": POLYGON_PLAN,
        "as_of": datetime.utcnow().isoformat(),
        "symbols": MARKET_SNAPSHOT_SYMBOLS,
    }
    market_snapshot_cache["payload"] = payload
    market_snapshot_cache["expires_at"] = monotonic() + MARKET_CACHE_TTL_SECONDS
    return payload

# Clerk auth
clerk_config = ClerkConfig(
    jwks_url=os.getenv("CLERK_JWKS_URL"),
    leeway=10.0,
)
clerk_guard = ClerkHTTPBearer(
    clerk_config,
    debug_mode=True,
)

async def get_current_user_id(creds: HTTPAuthorizationCredentials = Depends(clerk_guard)) -> str:
    user_id = creds.decoded["sub"]
    logger.info(f"Authenticated user: {user_id}")
    return user_id

# Models
class UserResponse(BaseModel):
    user: Dict[str, Any]
    created: bool

class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    years_until_retirement: Optional[int] = None
    target_retirement_income: Optional[float] = None
    asset_class_targets: Optional[Dict[str, float]] = None
    region_targets: Optional[Dict[str, float]] = None

class AccountUpdate(BaseModel):
    account_name: Optional[str] = None
    account_purpose: Optional[str] = None
    cash_balance: Optional[float] = None

class PositionUpdate(BaseModel):
    quantity: Optional[float] = None

class AnalyzeRequest(BaseModel):
    analysis_type: str = Field(default="portfolio")
    options: Dict[str, Any] = Field(default_factory=dict)

class AnalyzeResponse(BaseModel):
    job_id: str
    message: str

# Health
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/api/user", response_model=UserResponse)
async def get_or_create_user(
    clerk_user_id: str = Depends(get_current_user_id),
    creds: HTTPAuthorizationCredentials = Depends(clerk_guard),
):
    """Get user or create if first time."""
    try:
        user = db.users.find_by_clerk_id(clerk_user_id)
        if user:
            return UserResponse(user=user, created=False)

        token_data = creds.decoded
        display_name = token_data.get("name") or token_data.get("email", "").split("@")[0] or "New User"
        user_data = {
            "clerk_user_id": clerk_user_id,
            "display_name": display_name,
            "years_until_retirement": 20,
            "target_retirement_income": 60000,
            "asset_class_targets": {"equity": 70, "fixed_income": 30},
            "region_targets": {"north_america": 50, "international": 50},
        }

        db.users.db.insert("users", user_data, returning="clerk_user_id")
        created_user = db.users.find_by_clerk_id(clerk_user_id)
        logger.info("Created new user: %s", clerk_user_id)
        return UserResponse(user=created_user, created=True)
    except Exception as e:
        logger.error("Error in get_or_create_user: %s", e)
        raise HTTPException(status_code=500, detail="Failed to load user profile")


@app.put("/api/user")
async def update_user(user_update: UserUpdate, clerk_user_id: str = Depends(get_current_user_id)):
    """Update user settings."""
    try:
        user = db.users.find_by_clerk_id(clerk_user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        update_data = user_update.model_dump(exclude_unset=True)
        db.users.db.update(
            "users",
            update_data,
            "clerk_user_id = :clerk_user_id",
            {"clerk_user_id": clerk_user_id},
        )
        return db.users.find_by_clerk_id(clerk_user_id)
    except Exception as e:
        logger.error("Error updating user: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/accounts")
async def list_accounts(clerk_user_id: str = Depends(get_current_user_id)):
    """List user's accounts."""
    try:
        return db.accounts.find_by_user(clerk_user_id)
    except Exception as e:
        logger.error("Error listing accounts: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/accounts")
async def create_account(account: AccountCreate, clerk_user_id: str = Depends(get_current_user_id)):
    """Create new account."""
    try:
        user = db.users.find_by_clerk_id(clerk_user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        account_id = db.accounts.create_account(
            clerk_user_id=clerk_user_id,
            account_name=account.account_name,
            account_purpose=account.account_purpose,
            cash_balance=getattr(account, "cash_balance", Decimal("0")),
        )
        return db.accounts.find_by_id(account_id)
    except Exception as e:
        logger.error("Error creating account: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/accounts/{account_id}")
async def update_account(
    account_id: str,
    account_update: AccountUpdate,
    clerk_user_id: str = Depends(get_current_user_id),
):
    """Update account."""
    try:
        account = db.accounts.find_by_id(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        if account.get("clerk_user_id") != clerk_user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        db.accounts.update(account_id, account_update.model_dump(exclude_unset=True))
        return db.accounts.find_by_id(account_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating account: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/accounts/{account_id}")
async def delete_account(account_id: str, clerk_user_id: str = Depends(get_current_user_id)):
    """Delete an account and all its positions."""
    try:
        account = db.accounts.find_by_id(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        if account.get("clerk_user_id") != clerk_user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        for position in db.positions.find_by_account(account_id):
            db.positions.delete(position["id"])
        db.accounts.delete(account_id)
        return {"message": "Account deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error deleting account: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/accounts/{account_id}/positions")
async def list_positions(account_id: str, clerk_user_id: str = Depends(get_current_user_id)):
    """Get positions for account."""
    try:
        account = db.accounts.find_by_id(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        if account.get("clerk_user_id") != clerk_user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        formatted_positions = []
        for pos in db.positions.find_by_account(account_id):
            formatted_positions.append({**pos, "instrument": db.instruments.find_by_symbol(pos["symbol"])})
        return {"positions": formatted_positions}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error listing positions: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/positions")
async def create_position(position: PositionCreate, clerk_user_id: str = Depends(get_current_user_id)):
    """Create position."""
    try:
        account = db.accounts.find_by_id(position.account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        if account.get("clerk_user_id") != clerk_user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        symbol = position.symbol.upper()
        instrument = db.instruments.find_by_symbol(symbol)
        if not instrument:
            from src.schemas import InstrumentCreate

            instrument_type = "stock" if len(symbol) <= 5 and symbol.isalpha() else "etf"
            db.instruments.create_instrument(
                InstrumentCreate(
                    symbol=symbol,
                    name=f"{symbol} - User Added",
                    instrument_type=instrument_type,
                    current_price=Decimal("0.00"),
                    allocation_regions={"north_america": 100.0},
                    allocation_sectors={"other": 100.0},
                    allocation_asset_class={"equity": 100.0}
                    if instrument_type == "stock"
                    else {"fixed_income": 100.0},
                )
            )

        position_id = db.positions.add_position(
            account_id=position.account_id,
            symbol=symbol,
            quantity=position.quantity,
        )
        return db.positions.find_by_id(position_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error creating position: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/positions/{position_id}")
async def update_position(
    position_id: str,
    position_update: PositionUpdate,
    clerk_user_id: str = Depends(get_current_user_id),
):
    """Update position."""
    try:
        position = db.positions.find_by_id(position_id)
        if not position:
            raise HTTPException(status_code=404, detail="Position not found")

        account = db.accounts.find_by_id(position["account_id"])
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        if account.get("clerk_user_id") != clerk_user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        db.positions.update(position_id, position_update.model_dump(exclude_unset=True))
        return db.positions.find_by_id(position_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating position: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/positions/{position_id}")
async def delete_position(position_id: str, clerk_user_id: str = Depends(get_current_user_id)):
    """Delete position."""
    try:
        position = db.positions.find_by_id(position_id)
        if not position:
            raise HTTPException(status_code=404, detail="Position not found")

        account = db.accounts.find_by_id(position["account_id"])
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        if account.get("clerk_user_id") != clerk_user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        db.positions.delete(position_id)
        return {"message": "Position deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error deleting position: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/instruments")
async def list_instruments(clerk_user_id: str = Depends(get_current_user_id)):
    """Get all available instruments for autocomplete."""
    try:
        return [
            {
                "symbol": inst["symbol"],
                "name": inst["name"],
                "instrument_type": inst["instrument_type"],
                "current_price": float(inst["current_price"]) if inst.get("current_price") else None,
            }
            for inst in db.instruments.find_all()
        ]
    except Exception as e:
        logger.error("Error fetching instruments: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/market-snapshot")
async def market_snapshot(clerk_user_id: str = Depends(get_current_user_id)):
    """Return delayed dashboard market data and recent news from Polygon."""
    try:
        return await fetch_polygon_market_snapshot()
    except Exception as e:
        logger.error("Error fetching market snapshot: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch delayed market snapshot")


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def trigger_analysis(request: AnalyzeRequest, clerk_user_id: str = Depends(get_current_user_id)):
    """Trigger portfolio analysis."""
    with observe() as observability:
        with observability.start_as_current_span(
            name="api_trigger_analysis",
            input={
                "analysis_type": request.analysis_type,
                "options": request.options,
                "clerk_user_id": clerk_user_id,
            },
            metadata={"service": "api", "route": "/api/analyze"},
        ) as span:
            try:
                user = db.users.find_by_clerk_id(clerk_user_id)
                if not user:
                    raise HTTPException(status_code=404, detail="User not found")

                job_id = db.jobs.create_job(
                    clerk_user_id=clerk_user_id,
                    job_type="portfolio_analysis",
                    request_payload=request.model_dump(),
                )
                span.update_trace(
                    name="portfolio_analysis_job",
                    user_id=clerk_user_id,
                    session_id=str(job_id),
                    metadata={
                        "service": "api",
                        "analysis_type": request.analysis_type,
                    },
                )
                mark_job_progress(
                    db,
                    str(job_id),
                    "queued",
                    message="Analysis request queued for the Financial Planner.",
                )
                observability.create_event(
                    name="analysis_job_created",
                    input={"job_id": str(job_id), "analysis_type": request.analysis_type},
                )

                if pubsub_publisher and PUBSUB_TOPIC:
                    message = {
                        "job_id": str(job_id),
                        "clerk_user_id": clerk_user_id,
                        "analysis_type": request.analysis_type,
                        "options": request.options,
                    }
                    topic_path = get_pubsub_topic_path()
                    pubsub_publisher.publish(topic_path, json.dumps(message).encode("utf-8"))
                    logger.info("Published analysis job to Pub/Sub: %s", job_id)
                    observability.create_event(
                        name="analysis_job_published",
                        input={"job_id": str(job_id), "topic": topic_path},
                    )
                else:
                    logger.warning("PUBSUB_TOPIC not configured, job created but not queued")
                    observability.create_event(
                        name="analysis_job_not_queued",
                        input={"job_id": str(job_id)},
                        status_message="PUBSUB_TOPIC not configured",
                    )

                response = AnalyzeResponse(
                    job_id=str(job_id),
                    message="Analysis started. Check job status for results.",
                )
                span.update(output=response.model_dump())
                return response
            except HTTPException as e:
                logger.error("Error triggering analysis: %s", e.detail)
                span.update(status_message=str(e.detail))
                raise
            except Exception as e:
                logger.error("Error triggering analysis: %s", e)
                span.update(status_message=str(e))
                raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str, clerk_user_id: str = Depends(get_current_user_id)):
    """Get job status and results."""
    try:
        job = db.jobs.find_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.get("clerk_user_id") != clerk_user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
        job["progress"] = derive_job_progress(job)
        return job
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting job status: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jobs")
async def list_jobs(clerk_user_id: str = Depends(get_current_user_id)):
    """List user's analysis jobs."""
    try:
        user_jobs = db.jobs.find_by_user(clerk_user_id, limit=100)
        user_jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        for job in user_jobs:
            job["progress"] = derive_job_progress(job)
        return {"jobs": user_jobs}
    except Exception as e:
        logger.error("Error listing jobs: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/reset-accounts")
async def reset_accounts(clerk_user_id: str = Depends(get_current_user_id)):
    """Delete all accounts for the current user."""
    try:
        user = db.users.find_by_clerk_id(clerk_user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        deleted_count = 0
        for account in db.accounts.find_by_user(clerk_user_id):
            try:
                db.accounts.delete(account["id"])
                deleted_count += 1
            except Exception as e:
                logger.warning("Could not delete account %s: %s", account["id"], e)

        return {"message": f"Deleted {deleted_count} account(s)", "accounts_deleted": deleted_count}
    except Exception as e:
        logger.error("Error resetting accounts: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/populate-test-data")
async def populate_test_data(clerk_user_id: str = Depends(get_current_user_id)):
    """Populate test data for the current user."""
    try:
        user = db.users.find_by_clerk_id(clerk_user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        missing_instruments = {
            "AAPL": {
                "name": "Apple Inc.",
                "type": "stock",
                "current_price": 195.89,
                "allocation_regions": {"north_america": 100},
                "allocation_sectors": {"technology": 100},
                "allocation_asset_class": {"equity": 100},
            },
            "AMZN": {
                "name": "Amazon.com Inc.",
                "type": "stock",
                "current_price": 178.35,
                "allocation_regions": {"north_america": 100},
                "allocation_sectors": {"consumer_discretionary": 100},
                "allocation_asset_class": {"equity": 100},
            },
            "NVDA": {
                "name": "NVIDIA Corporation",
                "type": "stock",
                "current_price": 522.74,
                "allocation_regions": {"north_america": 100},
                "allocation_sectors": {"technology": 100},
                "allocation_asset_class": {"equity": 100},
            },
            "MSFT": {
                "name": "Microsoft Corporation",
                "type": "stock",
                "current_price": 430.82,
                "allocation_regions": {"north_america": 100},
                "allocation_sectors": {"technology": 100},
                "allocation_asset_class": {"equity": 100},
            },
            "GOOGL": {
                "name": "Alphabet Inc. Class A",
                "type": "stock",
                "current_price": 173.69,
                "allocation_regions": {"north_america": 100},
                "allocation_sectors": {"technology": 100},
                "allocation_asset_class": {"equity": 100},
            },
        }

        for symbol, info in missing_instruments.items():
            if not db.instruments.find_by_symbol(symbol):
                try:
                    from src.schemas import InstrumentCreate

                    db.instruments.create_instrument(
                        InstrumentCreate(
                            symbol=symbol,
                            name=info["name"],
                            instrument_type=info["type"],
                            current_price=Decimal(str(info["current_price"])),
                            allocation_regions=info["allocation_regions"],
                            allocation_sectors=info["allocation_sectors"],
                            allocation_asset_class=info["allocation_asset_class"],
                        )
                    )
                    logger.info("Added missing instrument: %s", symbol)
                except Exception as e:
                    logger.warning("Could not add instrument %s: %s", symbol, e)

        accounts_data = [
            {
                "name": "401k Long-term",
                "purpose": "Primary retirement savings account with employer match",
                "cash": 5000.00,
                "positions": [("SPY", 150), ("VTI", 100), ("BND", 200), ("QQQ", 75), ("IWM", 50)],
            },
            {
                "name": "Roth IRA",
                "purpose": "Tax-free retirement growth account",
                "cash": 2500.00,
                "positions": [("VTI", 80), ("VXUS", 60), ("VNQ", 40), ("GLD", 25), ("TLT", 30), ("VIG", 45)],
            },
            {
                "name": "Brokerage Account",
                "purpose": "Taxable investment account for individual stocks",
                "cash": 10000.00,
                "positions": [("TSLA", 15), ("AAPL", 50), ("AMZN", 10), ("NVDA", 25), ("MSFT", 30), ("GOOGL", 20)],
            },
        ]

        created_accounts = []
        for account_data in accounts_data:
            account_id = db.accounts.create_account(
                clerk_user_id=clerk_user_id,
                account_name=account_data["name"],
                account_purpose=account_data["purpose"],
                cash_balance=Decimal(str(account_data["cash"])),
            )

            for symbol, quantity in account_data["positions"]:
                try:
                    db.positions.add_position(
                        account_id=account_id,
                        symbol=symbol,
                        quantity=Decimal(str(quantity)),
                    )
                except Exception as e:
                    logger.warning("Could not add position %s: %s", symbol, e)

            created_accounts.append(account_id)

        all_accounts = []
        for account_id in created_accounts:
            account = db.accounts.find_by_id(account_id)
            account["positions"] = db.positions.find_by_account(account_id)
            all_accounts.append(account)

        return {
            "message": "Test data populated successfully",
            "accounts_created": len(created_accounts),
            "accounts": all_accounts,
        }
    except Exception as e:
        logger.error("Error populating test data: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
