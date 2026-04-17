"""
Minimal OpenAI tracing helpers shared by the Alex agents.
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from agents import custom_span, set_default_openai_client, set_tracing_export_api_key, trace
from agents.tracing.processors import default_processor
from openai import AsyncOpenAI

logger = logging.getLogger()

_openai_client: AsyncOpenAI | None = None
_tracing_configured = False
MAX_TRACE_FIELD_CHARS = 4000
MAX_TRACE_BLOB_CHARS = 8000


def serialize_for_trace(value: Any) -> Any:
    """Convert values into JSON-serializable trace data."""
    if value is None:
        return None

    try:
        return json.loads(json.dumps(value, default=str))
    except Exception:
        return str(value)


def dump_trace_json(value: Any) -> str:
    """Serialize trace data to a JSON string for function spans."""
    return trim_trace_text(json.dumps(serialize_for_trace(value), default=str), MAX_TRACE_BLOB_CHARS)


def trim_trace_text(value: str, limit: int = MAX_TRACE_FIELD_CHARS) -> str:
    """Trim trace text to stay within exporter payload limits."""
    if len(value) <= limit:
        return value

    overflow = len(value) - limit
    suffix = f"... [truncated {overflow} chars]"
    return value[: max(0, limit - len(suffix))] + suffix


def stringify_for_trace(value: Any, limit: int = MAX_TRACE_FIELD_CHARS) -> str:
    """Convert a value into a bounded JSON string for trace metadata/data fields."""
    try:
        serialized = json.dumps(serialize_for_trace(value), default=str)
    except Exception:
        serialized = str(value)
    return trim_trace_text(serialized, limit)


def configure_openai_tracing() -> AsyncOpenAI | None:
    """Initialize the shared OpenAI client once and wire tracing export."""
    global _openai_client, _tracing_configured

    if _tracing_configured:
        return _openai_client

    _tracing_configured = True

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OpenAI tracing disabled: OPENAI_API_KEY is not set")
        return None

    _openai_client = AsyncOpenAI(api_key=api_key)
    set_default_openai_client(_openai_client, use_for_tracing=True)
    set_tracing_export_api_key(api_key)
    logger.info("OpenAI tracing configured")
    return _openai_client


def flush_openai_tracing() -> None:
    """Force-flush the default tracing processor."""
    try:
        default_processor().force_flush()
    except Exception as exc:
        logger.warning(f"OpenAI tracing flush failed: {exc}")


@contextmanager
def observe() -> Iterator[None]:
    """Configure tracing for the current process and flush on exit."""
    configure_openai_tracing()
    try:
        yield None
    finally:
        flush_openai_tracing()


@dataclass
class AgentTraceRecorder:
    """Mutable trace payload recorder for an agent execution."""

    span: Any
    payload: dict[str, Any]

    def record_output(self, output: Any) -> None:
        self.payload["output"] = stringify_for_trace(output, MAX_TRACE_BLOB_CHARS)

    def record_error(self, error: Exception) -> None:
        error_payload = {
            "type": type(error).__name__,
            "message": str(error),
        }
        self.payload["error"] = stringify_for_trace(error_payload)
        self.span.set_error({"message": str(error), "data": error_payload})


@contextmanager
def traced_agent_execution(
    agent_name: str,
    job_id: str | None,
    input_payload: Any,
) -> Iterator[AgentTraceRecorder]:
    """
    Create a top-level OpenAI trace plus a custom execution span for one agent run.
    """
    configure_openai_tracing()

    trace_metadata = {
        "agent_name": agent_name,
        "job_id": str(job_id) if job_id is not None else "",
        "input_payload": stringify_for_trace(input_payload),
    }
    span_payload = {
        "agent_name": agent_name,
        "job_id": str(job_id) if job_id is not None else "",
        "input_payload": stringify_for_trace(input_payload, MAX_TRACE_BLOB_CHARS),
        "output": None,
        "error": None,
    }

    with trace(
        workflow_name=f"{agent_name}_execution",
        group_id=job_id,
        metadata=trace_metadata,
    ):
        with custom_span(name="agent_execution", data=span_payload) as execution_span:
            recorder = AgentTraceRecorder(span=execution_span, payload=span_payload)
            try:
                yield recorder
            except Exception as exc:
                recorder.record_error(exc)
                raise
