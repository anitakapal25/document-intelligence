"""Optional Phoenix tracing with metadata only; no source or output capture."""

import os
from contextlib import nullcontext

ALLOWED_ATTRIBUTES = {"parser", "pdf_sha256", "pages", "chunks", "status",
                      "input_tokens", "output_tokens", "elapsed_ms"}


def start_tracing():
    """Return a tracer only when an explicit collector endpoint is configured."""
    endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT")
    if not endpoint:
        return None
    from phoenix.otel import register

    provider = register(endpoint=endpoint, project_name="document-intelligence-pilot",
                        protocol="http/protobuf", auto_instrument=False, verbose=False)
    return provider.get_tracer("document-intelligence")


def metadata_span(tracer, name: str, **attributes):
    if tracer is None:
        return nullcontext()
    safe = {key: value for key, value in attributes.items()
            if key in ALLOWED_ATTRIBUTES and isinstance(value, (str, int, float, bool))
            and value is not None}
    return tracer.start_as_current_span(name, attributes=safe)


def finish_tracing(tracer):
    if tracer is not None:
        from opentelemetry import trace
        trace.get_tracer_provider().force_flush(timeout_millis=5000)
