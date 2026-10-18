"""Verify parser-neutral chunk provenance and field merging without API calls."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

from app.parsers import ParsedDocument, ParsedPage, parse_llamaparse
from app.pdf_workflow import _merge_parties, extract_parsed, page_chunks
from app.schemas import FieldStatus, ModelExtraction, PartiesField, RunStatus


class FakeResponses:
    def parse(self, **kwargs):
        source = kwargs["input"][1]["content"]
        is_second_page = "Illinois law" in source
        parsed = ModelExtraction.model_validate({
            "document_name": {"status": "missing", "value": None, "evidence": []},
            "parties": {"status": "missing", "value": [], "evidence": []},
            "agreement_date": {"status": "missing", "value": None, "evidence": []},
            "effective_date": {"status": "missing", "value": None, "evidence": []},
            "governing_law": {
                "status": "found" if is_second_page else "missing",
                "value": "Illinois" if is_second_page else None,
                "evidence": [{"quote": "Illinois law"}] if is_second_page else [],
            },
        })
        return SimpleNamespace(status="completed", output_parsed=parsed, output=[], usage=None, id=None)


class PdfWorkflowTests(unittest.TestCase):
    def test_party_punctuation_variants_deduplicate(self):
        fields = [
            PartiesField(status=FieldStatus.FOUND, value=["Electric City of Illinois LLC"], evidence=[], issue=None),
            PartiesField(status=FieldStatus.FOUND, value=["Electric City of Illinois L.L.C."], evidence=[], issue=None),
        ]
        self.assertEqual(_merge_parties(fields).value, ["Electric City of Illinois LLC"])

    def test_llamaparse_uses_reported_page_numbers(self):
        pages = [SimpleNamespace(success=True, page_number=3, markdown="Law of Illinois")]
        fake_client = SimpleNamespace(
            files=SimpleNamespace(create=lambda **kwargs: SimpleNamespace(id="file-1")),
            parsing=SimpleNamespace(parse=lambda **kwargs: SimpleNamespace(
                markdown=SimpleNamespace(pages=pages))),
        )
        with patch.dict("os.environ", {"LLAMA_CLOUD_API_KEY": "test-only"}):
            with patch("llama_cloud.LlamaCloud", return_value=fake_client):
                parsed = parse_llamaparse(Path("sample.pdf"))
        self.assertEqual(parsed.pages[0].number, 3)

    def test_page_metadata_and_evidence(self):
        parsed = ParsedDocument(parser="docling", pages=[
            ParsedPage(number=1, text="SERVICES AGREEMENT. Acme and Beta."),
            ParsedPage(number=2, text="This contract is governed by Illinois law."),
        ])
        self.assertEqual([page for page, _ in page_chunks(parsed)], [1, 2])
        client = SimpleNamespace(responses=FakeResponses())
        run = extract_parsed("sample", parsed, client=client)
        self.assertEqual(run.status, RunStatus.COMPLETED)
        evidence = run.extraction.governing_law.evidence[0]
        self.assertEqual(evidence.page, 2)
        self.assertEqual(parsed.pages[1].text[evidence.start:evidence.end], evidence.quote)


if __name__ == "__main__":
    unittest.main()
