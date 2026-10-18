"""Contract text must not enter Phoenix span attributes."""

import unittest

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.tracing import metadata_span


class TracingTests(unittest.TestCase):
    def test_only_allowlisted_metadata_is_recorded(self):
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        with metadata_span(provider.get_tracer(__name__), "parse_pdf", parser="docling",
                           pages=2, source_text="CONFIDENTIAL CONTRACT", pdf_sha256="abc"):
            pass
        attributes = exporter.get_finished_spans()[0].attributes
        self.assertEqual(attributes["pages"], 2)
        self.assertNotIn("source_text", attributes)
        self.assertNotIn("CONFIDENTIAL CONTRACT", str(attributes))


if __name__ == "__main__":
    unittest.main()
