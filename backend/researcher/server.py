"""
Alex Researcher Service - Investment Advice Agent (Vertex Native)
"""

import os
import logging
from datetime import datetime, UTC
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

import vertexai
from vertexai.preview.generative_models import GenerativeModel

# Silence noise
logging.basicConfig(level=logging.INFO)

from context import get_agent_instructions, DEFAULT_RESEARCH_PROMPT

load_dotenv(override=True)

app = FastAPI(title="Alex Researcher Service")


class ResearchRequest(BaseModel):
    topic: Optional[str] = None


# ✅ AUTH
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "alex-vertex-sa.json"

# ✅ INIT (KEEP us-east4)
vertexai.init(
    project="alex-prod-project",
    location="us-east4"
)

# ✅ WORKING MODEL (from your Studio)
model = GenerativeModel("gemini-2.5-flash")


async def run_research_agent(topic: str = None) -> str:
    if topic:
        prompt = f"""
You are an investment research analyst.

Research the following topic and provide:
- Key trends
- Risks
- Opportunities
- Final recommendation

Topic: {topic}
"""
    else:
        prompt = DEFAULT_RESEARCH_PROMPT

    try:
        response = model.generate_content(prompt)

        # ✅ safer extraction (handles structured responses)
        if hasattr(response, "text") and response.text:
            return response.text

        # fallback (rare cases)
        return str(response)

    except Exception as e:
        raise Exception(f"Vertex call failed: {str(e)}")


@app.post("/research")
async def research(request: ResearchRequest) -> str:
    try:
        return await run_research_agent(request.topic)
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "model": "gemini-3.1-pro-preview",  # ✅ fixed
        "region": "us-east4",
        "timestamp": datetime.now(UTC).isoformat(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)