import json
import unittest
from types import SimpleNamespace

import httpx
from openai import APITimeoutError, OpenAI

from app.evidence import locate, validate_extraction
from app.extractor import MAX_SOURCE_CHARS, extract_text
from app.schemas import FieldStatus, ModelExtraction, RunStatus


SOURCE = (
    "SERVICES AGREEMENT. Acme Ltd and Beta Inc signed on January 2, 2024. "
    "Effective upon delivery. This agreement is governed by Illinois law."
)


def model_data() -> dict:
    return {
        "document_name": {"status": "found", "value": "Services Agreement", "evidence": [{"quote": "SERVICES AGREEMENT"}]},
        "parties": {"status": "found", "value": ["Acme Ltd", "Beta Inc"], "evidence": [{"quote": "Acme Ltd"}, {"quote": "Beta Inc"}]},
        "agreement_date": {"status": "found", "value": "2024-01-02", "evidence": [{"quote": "January 2, 2024"}]},
        "effective_date": {"status": "ambiguous", "value": None, "evidence": [{"quote": "Effective upon delivery"}]},
        "governing_law": {"status": "found", "value": "Illinois, US", "evidence": [{"quote": "Illinois law"}]},
    }


class FakeResponses:
    def __init__(self, response=None, failures=0):
        self.response = response
        self.failures = failures
        self.calls = 0

    def parse(self, **kwargs):
        self.calls += 1
        if self.calls <= self.failures:
            raise APITimeoutError(request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
        return self.response


class TextExtractionTests(unittest.TestCase):
    def test_valid_evidence_and_ambiguous_date(self):
        model = ModelExtraction.model_validate(model_data())
        result = validate_extraction(model, SOURCE)
        self.assertEqual(result.agreement_date.value, "2024-01-02")
        self.assertEqual(result.effective_date.status, FieldStatus.AMBIGUOUS)
        self.assertIsNone(result.effective_date.value)
        self.assertEqual(result.parties.value, ["Acme Ltd", "Beta Inc"])
        self.assertEqual(result.parties.evidence[0].start, SOURCE.index("Acme Ltd"))
        self.assertIsNone(result.parties.evidence[0].page)

    def test_unsupported_quote_fails_field(self):
        data = model_data()
        data["governing_law"]["evidence"] = [{"quote": "California law"}]
        result = validate_extraction(ModelExtraction.model_validate(data), SOURCE)
        self.assertEqual(result.governing_law.status, FieldStatus.FAILED)
        self.assertEqual(result.governing_law.issue, "evidence_not_in_source")

    def test_whitespace_variation_maps_to_verbatim_source_span(self):
        source = "Parties: Electric City of\n  Illinois LLC."
        evidence = locate("Electric City of Illinois LLC", source)
        self.assertIsNotNone(evidence)
        self.assertEqual(evidence.quote, "Electric City of\n  Illinois LLC")
        self.assertEqual(source[evidence.start:evidence.end], evidence.quote)
        self.assertIsNone(locate("Electric City of Ohio LLC", source))

    def test_invalid_iso_date_fails_field(self):
        data = model_data()
        data["agreement_date"]["value"] = "2024-02-30"
        result = validate_extraction(ModelExtraction.model_validate(data), SOURCE)
        self.assertEqual(result.agreement_date.status, FieldStatus.FAILED)

    def test_completed_response_and_usage(self):
        response = SimpleNamespace(
            status="completed",
            output_parsed=ModelExtraction.model_validate(model_data()),
            output=[],
            usage=SimpleNamespace(input_tokens=120, output_tokens=80),
            id="test-response",
        )
        fake = SimpleNamespace(responses=FakeResponses(response))
        run = extract_text("sample", SOURCE, client=fake)
        self.assertEqual(run.status, RunStatus.COMPLETED)
        self.assertEqual(run.metadata.input_tokens, 120)

    def test_refusal_and_incomplete(self):
        refusal = SimpleNamespace(
            status="completed", output_parsed=None,
            output=[SimpleNamespace(content=[SimpleNamespace(type="refusal")])],
        )
        fake = SimpleNamespace(responses=FakeResponses(refusal))
        self.assertEqual(extract_text("sample", SOURCE, client=fake).status, RunStatus.REFUSED)
        incomplete = SimpleNamespace(status="incomplete", output_parsed=None, output=[])
        fake = SimpleNamespace(responses=FakeResponses(incomplete))
        self.assertEqual(extract_text("sample", SOURCE, client=fake).status, RunStatus.INCOMPLETE)

    def test_empty_and_oversized_source_do_not_call_model(self):
        responses = FakeResponses()
        fake = SimpleNamespace(responses=responses)
        self.assertEqual(extract_text("sample", " ", client=fake).error_code, "empty_source")
        self.assertEqual(
            extract_text("sample", "x" * (MAX_SOURCE_CHARS + 1), client=fake).error_code,
            "source_needs_chunking",
        )
        self.assertEqual(responses.calls, 0)

    def test_bounded_retry(self):
        response = SimpleNamespace(
            status="completed", output_parsed=ModelExtraction.model_validate(model_data()),
            output=[], usage=None, id=None,
        )
        responses = FakeResponses(response, failures=2)
        run = extract_text("sample", SOURCE, client=SimpleNamespace(responses=responses), sleep=lambda _: None)
        self.assertEqual(run.status, RunStatus.COMPLETED)
        self.assertEqual(responses.calls, 3)

    def test_openai_sdk_parses_schema_from_http_response(self):
        def handler(request):
            self.assertEqual(request.url.path, "/v1/responses")
            body = json.loads(request.content)
            self.assertEqual(body["model"], "gpt-6-luna")
            self.assertIs(body["store"], False)
            return httpx.Response(200, json={
                "id": "mock-response",
                "object": "response",
                "created_at": 0,
                "model": "gpt-6-luna",
                "status": "completed",
                "output": [{
                    "type": "message", "id": "msg-1", "role": "assistant", "status": "completed",
                    "content": [{"type": "output_text", "text": json.dumps(model_data()), "annotations": []}],
                }],
                "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            })

        http_client = httpx.Client(transport=httpx.MockTransport(handler))
        client = OpenAI(api_key="test-only", http_client=http_client, max_retries=0)
        run = extract_text("sample", SOURCE, client=client)
        self.assertEqual(run.status, RunStatus.COMPLETED)
        self.assertEqual(run.extraction.governing_law.value, "Illinois, US")
        self.assertEqual(run.metadata.response_id, "mock-response")


if __name__ == "__main__":
    unittest.main()
