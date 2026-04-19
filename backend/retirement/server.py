"""Cloud Run HTTP wrapper for the retirement service."""

import json

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from lambda_handler import handle_retirement_event

app = FastAPI(title="Alex Retirement Service")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "retirement"}


@app.post("/retirement")
async def retirement(request: Request) -> JSONResponse:
    payload = await request.json()
    result = await handle_retirement_event(payload)
    status_code = result.get("statusCode", 200)
    body = result.get("body", "{}")
    try:
        content = json.loads(body)
    except json.JSONDecodeError:
        content = {"message": body}
    return JSONResponse(status_code=status_code, content=content)
