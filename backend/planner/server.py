"""Cloud Run HTTP wrapper for the planner service."""

import asyncio
import json

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from lambda_handler import lambda_handler

app = FastAPI(title="Alex Planner Service")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "planner"}


@app.post("/pubsub/push")
async def pubsub_push(request: Request) -> JSONResponse:
    payload = await request.json()
    result = await asyncio.to_thread(lambda_handler, payload, None)
    status_code = result.get("statusCode", 200)
    body = result.get("body", "{}")
    try:
        content = json.loads(body)
    except json.JSONDecodeError:
        content = {"message": body}
    return JSONResponse(status_code=status_code, content=content)
