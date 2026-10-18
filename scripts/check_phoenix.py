"""Emit one metadata-only trace to a configured Phoenix collector."""

from app.tracing import finish_tracing, metadata_span, start_tracing


def main() -> None:
    tracer = start_tracing()
    if tracer is None:
        raise SystemExit("Set PHOENIX_COLLECTOR_ENDPOINT first")
    with metadata_span(tracer, "phoenix_connection_check", status="completed", pages=0):
        pass
    finish_tracing(tracer)
    print("Sent Phoenix connection-check span; verify it appears in the local UI")


if __name__ == "__main__":
    main()
