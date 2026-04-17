"""Alex Researcher Service for Cloud Run."""

import logging
import os
from datetime import UTC, datetime
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import vertexai
from vertexai.preview.generative_models import GenerativeModel

from context import DEFAULT_RESEARCH_PROMPT

load_dotenv(override=True)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Alex Researcher Service")


class ResearchRequest(BaseModel):
    topic: Optional[str] = None


def get_runtime_config() -> tuple[str, str, str]:
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    region = os.getenv("VERTEX_REGION", "us-east4")
    model_name = os.getenv("VERTEX_MODEL", "gemini-2.5-flash")
    return project_id, region, model_name


def get_model() -> GenerativeModel:
    project_id, region, model_name = get_runtime_config()
    if not project_id:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT is required")
    vertexai.init(project=project_id, location=region)
    return GenerativeModel(model_name)


async def run_research_agent(topic: str | None = None) -> str:
    prompt = (
        f"""You are an investment research analyst.

Research the following topic and provide:
- Key trends
- Risks
- Opportunities
- Final recommendation

Topic: {topic}
"""
        if topic
        else DEFAULT_RESEARCH_PROMPT
    )

    try:
        response = get_model().generate_content(prompt)
        if hasattr(response, "text") and response.text:
            return response.text
        return str(response)
    except Exception as exc:
        raise RuntimeError(f"Vertex call failed: {exc}") from exc


@app.post("/research")
async def research(request: ResearchRequest) -> dict[str, str]:
    try:
        content = await run_research_agent(request.topic)
        return {"content": content}
    except Exception as exc:
        logger.exception("Research request failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/research/auto")
async def research_auto() -> dict[str, str]:
    try:
        content = await run_research_agent()
        return {"content": content}
    except Exception as exc:
        logger.exception("Automated research request failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/health")
async def health() -> dict[str, str]:
    project_id, region, model_name = get_runtime_config()
    return {
        "status": "healthy",
        "project": project_id,
        "model": model_name,
        "region": region,
        "timestamp": datetime.now(UTC).isoformat(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
