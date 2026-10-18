"""API contract checks without paid model or parser calls."""

import hashlib
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api import MAX_UPLOAD_BYTES, allowed_pdfs, app, get_budget
from app.budget import BudgetExceeded, MemoryBudget, period_now
from app.parsers import ParsedDocument, ParsedPage
from app.schemas import Extraction, ExtractionRun, FieldStatus, PartiesField, RunMetadata, RunStatus, ScalarField


PDF = b"%PDF-1.4\nsynthetic test PDF bytes\n%%EOF"


def sample_run(status=RunStatus.COMPLETED):
    missing = ScalarField(status=FieldStatus.MISSING, value=None, evidence=[], issue=None)
    extraction = Extraction(document_name=missing, parties=PartiesField(
        status=FieldStatus.MISSING, value=[], evidence=[], issue=None),
        agreement_date=missing, effective_date=missing, governing_law=missing)
    return ExtractionRun(document_id="sample", status=status,
                         extraction=extraction if status == RunStatus.COMPLETED else None,
                         metadata=RunMetadata(model="gpt-6-luna", source="pdf:docling",
                                              prompt_version="text-v2", elapsed_ms=1,
                                              input_tokens=100, output_tokens=50, response_id=None),
                         error_code="model_refusal" if status == RunStatus.REFUSED else None)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.budget = MemoryBudget()
        app.dependency_overrides[get_budget] = lambda: self.budget
        self.client = TestClient(app)
        self.allowlist = patch("app.api.allowed_pdfs", return_value={hashlib.sha256(PDF).hexdigest(): "sample"})
        self.allowlist.start()

    def tearDown(self):
        self.allowlist.stop()
        app.dependency_overrides.clear()
        self.client.close()

    def upload(self, contents=PDF, name="sample.pdf", mime="application/pdf"):
        return self.client.post("/extract", files={"file": (name, contents, mime)})

    def test_health_and_page(self):
        self.assertEqual(self.client.get("/health").json()["status"], "ok")
        self.assertIn("Upload one listed CUAD", self.client.get("/").text)

    def test_valid_pdf_and_absent_fields(self):
        parsed = ParsedDocument(parser="docling", pages=[ParsedPage(number=1, text="sample")])
        with patch("app.api.parse_pdf", return_value=parsed), \
             patch("app.api.extract_parsed", return_value=sample_run()):
            response = self.upload()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["extraction"]["parties"]["status"], "missing")
        self.assertEqual(self.budget.totals[period_now()]["reserved"], 0)

    def test_type_size_and_scope(self):
        self.assertEqual(self.upload(name="sample.txt").status_code, 415)
        self.assertEqual(self.upload(contents=b"not a pdf").status_code, 415)
        self.assertEqual(self.upload(contents=PDF + b"extra").json()["detail"]["code"], "outside_pilot_scope")
        self.assertEqual(self.upload(contents=PDF + b"x" * MAX_UPLOAD_BYTES).status_code, 413)

    def test_parser_failure_and_refusal(self):
        with patch("app.api.parse_pdf", side_effect=ValueError("bad PDF")):
            response = self.upload()
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["code"], "pdf_parse_failed")
        parsed = ParsedDocument(parser="docling", pages=[ParsedPage(number=1, text="sample")])
        with patch("app.api.parse_pdf", return_value=parsed), \
             patch("app.api.extract_parsed", return_value=sample_run(RunStatus.REFUSED)):
            response = self.upload()
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["status"], "refused")

    def test_budget_limit(self):
        self.budget.totals[period_now()] = {"spent": 5_000_000, "reserved": 0}
        response = self.upload()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["detail"]["code"], "monthly_budget_limit")

    def test_parser_exception_text_is_not_logged(self):
        with patch("app.api.parse_pdf", side_effect=RuntimeError("private contract text")), \
             self.assertLogs("app.api", level="ERROR") as captured:
            response = self.upload()
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("private contract text", "\n".join(captured.output))
        self.assertNotIn("private contract text", response.text)
        self.assertEqual(self.budget.totals[period_now()]["reserved"], 0)


class DemoScopeTests(unittest.TestCase):
    def tearDown(self):
        allowed_pdfs.cache_clear()

    def test_demo_sample_and_excluded_documents(self):
        with patch.dict(os.environ, {"PILOT_SCOPE": "development"}):
            allowed_pdfs.cache_clear()
            development = allowed_pdfs()
        with patch.dict(os.environ, {"PILOT_SCOPE": "demo"}), TestClient(app) as client:
            allowed_pdfs.cache_clear()
            demo = allowed_pdfs()
            self.assertEqual(len(demo), 4)
            self.assertTrue(set(demo) < set(development))
            self.assertEqual(client.get("/scope").json()["documents"], sorted(demo.values()))
            sample = client.get("/sample.pdf")
            self.assertEqual(sample.status_code, 200)
            self.assertEqual(demo[hashlib.sha256(sample.content).hexdigest()],
                             "synthetic-sample-agreement")

    def test_unknown_scope_fails_closed(self):
        with patch.dict(os.environ, {"PILOT_SCOPE": "typo"}):
            allowed_pdfs.cache_clear()
            with self.assertRaisesRegex(RuntimeError, "Unsupported PILOT_SCOPE"):
                allowed_pdfs()


if __name__ == "__main__":
    unittest.main()
