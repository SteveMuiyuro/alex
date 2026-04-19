"""
Minimal OpenAI tracing helpers shared by the Alex agents.
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from typing import Any, Iterator

from agents import custom_span, set_default_openai_client, set_tracing_export_api_key, trace
from agents.tracing.processors import default_processor
from openai import AsyncOpenAI

logger = logging.getLogger()

_openai_client: AsyncOpenAI | None = None
_tracing_configured = False
_langfuse_client: Any | None = None
_langfuse_configured = False
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
        logger.info("OpenAI tracing disabled: OPENAI_API_KEY is not set")
        return None

    _openai_client = AsyncOpenAI(api_key=api_key)
    set_default_openai_client(_openai_client, use_for_tracing=True)
    set_tracing_export_api_key(api_key)
    logger.info("OpenAI tracing configured")
    return _openai_client


def configure_langfuse() -> Any | None:
    """Initialize the shared Langfuse client once when credentials are available."""
    global _langfuse_client, _langfuse_configured

    if _langfuse_configured:
        return _langfuse_client

    _langfuse_configured = True

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_BASE_URL") or os.getenv("LANGFUSE_HOST")

    if not public_key or not secret_key:
        logger.info("Langfuse tracing disabled: Langfuse credentials are not set")
        return None

    try:
        from langfuse import Langfuse

        kwargs: dict[str, Any] = {
            "public_key": public_key,
            "secret_key": secret_key,
        }
        if host:
            kwargs["host"] = host

        _langfuse_client = Langfuse(**kwargs)
        logger.info("Langfuse tracing configured")
        return _langfuse_client
    except Exception as exc:
        logger.warning(f"Langfuse tracing disabled: failed to initialize client: {exc}")
        _langfuse_client = None
        return None


def flush_openai_tracing() -> None:
    """Force-flush the default tracing processor."""
    try:
        default_processor().force_flush()
    except Exception as exc:
        logger.warning(f"OpenAI tracing flush failed: {exc}")


def flush_langfuse() -> None:
    """Force-flush the shared Langfuse client when enabled."""
    if _langfuse_client is None:
        return

    try:
        _langfuse_client.flush()
    except Exception as exc:
        logger.warning(f"Langfuse flush failed: {exc}")


class NoopWorkflowSpan:
    """No-op Langfuse span replacement used when Langfuse is disabled."""

    def update(self, **_: Any) -> "NoopWorkflowSpan":
        return self

    def update_trace(self, **_: Any) -> "NoopWorkflowSpan":
        return self

    def score(self, **_: Any) -> None:
        return None

    def create_event(self, **_: Any) -> "NoopWorkflowSpan":
        return self

    def start_as_current_span(self, **_: Any):
        return nullcontext(NoopWorkflowSpan())


@dataclass
class WorkflowObserver:
    """Thin wrapper around Langfuse used for workflow-level spans and events."""

    client: Any | None = None

    def __bool__(self) -> bool:
        return self.client is not None

    def start_as_current_span(self, **kwargs: Any):
        if self.client is None:
            return nullcontext(NoopWorkflowSpan())
        return self.client.start_as_current_span(**kwargs)

    def create_event(self, **kwargs: Any) -> Any | None:
        if self.client is None:
            return None
        return self.client.create_event(**kwargs)


def get_workflow_observer() -> WorkflowObserver:
    """Return the shared workflow observer for manual span creation."""
    return WorkflowObserver(client=configure_langfuse())


@contextmanager
def observe() -> Iterator[WorkflowObserver]:
    """Configure OpenAI and Langfuse tracing for the current process and flush on exit."""
    configure_openai_tracing()
    workflow_observer = get_workflow_observer()
    try:
        yield workflow_observer
    finally:
        flush_langfuse()
        flush_openai_tracing()


@dataclass
class AgentTraceRecorder:
    """Mutable trace payload recorder for an agent execution."""

    span: Any
    payload: dict[str, Any]

    def record_output(self, output: Any) -> None:
        if output is not None:
            self.payload["output"] = stringify_for_trace(output, MAX_TRACE_BLOB_CHARS)

    def record_error(self, error: Exception) -> None:
        error_payload = {
            "type": type(error).__name__,
            "message": str(error),
        }
        self.payload["error"] = stringify_for_trace(error_payload)
        self.span.set_error(trim_trace_text(str(error)))


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
