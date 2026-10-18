import json
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class DevelopmentReferenceTests(unittest.TestCase):
    def test_references_match_manifest_and_source_spans(self):
        manifest = json.loads((ROOT / "manifests/development.json").read_text(encoding="utf-8"))
        references = json.loads((ROOT / "references/development.json").read_text(encoding="utf-8"))
        dataset = json.loads(
            (ROOT / "data/raw/cuad_benchmark/train_separate_questions.json").read_text(encoding="utf-8")
        )
        source = {contract["title"]: contract for contract in dataset["data"]}
        self.assertEqual(
            [item["title"] for item in references["contracts"]],
            [item["title"] for item in manifest["contracts"]],
        )

        for item in references["contracts"]:
            contract = source[item["title"]]
            self.assertEqual(len(item["fields"]), 5)
            for field_name, field in item["fields"].items():
                if field["status"] == "missing":
                    self.assertIsNone(field["value"])
                    self.assertFalse(field["source_spans"])
                if field["status"] == "found":
                    self.assertTrue(field["value"])
                    self.assertTrue(field["source_spans"])
                if field_name in ("Agreement Date", "Effective Date") and field["status"] == "found":
                    self.assertEqual(date.fromisoformat(field["value"]).isoformat(), field["value"])
                for span in field["source_spans"]:
                    paragraph = contract["paragraphs"][span["paragraph"]]
                    quote = paragraph["context"][span["start"]:span["end"]]
                    if span.get("origin") == "manual_review":
                        self.assertIsNone(span["qa_id"])
                        self.assertTrue(quote.strip())
                    else:
                        qa = next(q for q in paragraph["qas"] if q["id"] == span["qa_id"])
                        self.assertIn(quote, [answer["text"] for answer in qa["answers"]])


if __name__ == "__main__":
    unittest.main()
