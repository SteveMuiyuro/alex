"""Cloud Run HTTP wrapper for the tagger service."""

import json

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from lambda_handler import handle_tagger_event

app = FastAPI(title="Alex Tagger Service")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "tagger"}


@app.post("/tag")
async def tag(request: Request) -> JSONResponse:
    payload = await request.json()
    result = await handle_tagger_event(payload)
    status_code = result.get("statusCode", 200)
    body = result.get("body", "{}")
    try:
        content = json.loads(body)
    except json.JSONDecodeError:
        content = {"message": body}
    return JSONResponse(status_code=status_code, content=content)
