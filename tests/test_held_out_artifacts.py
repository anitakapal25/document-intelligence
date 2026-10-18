"""Check reference evidence and frozen experiment provenance without paid calls."""
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class HeldOutArtifactTests(unittest.TestCase):
    def test_references_cover_manifest_and_define_exclusions(self):
        manifest = json.loads((ROOT / "manifests/held_out.json").read_text())
        refs = json.loads((ROOT / "references/held_out.json").read_text())
        self.assertEqual([c["title"] for c in manifest["contracts"]], [c["title"] for c in refs["contracts"]])
        excluded = [f for c in refs["contracts"] for f in c["fields"].values() if f["status"] == "unscorable"]
        self.assertEqual({f["value"] for f in excluded}, {"New Jersey, US", "Delaware, US"})
        for c in refs["contracts"]:
            self.assertEqual(len(c["fields"]), 5)
            for field in c["fields"].values():
                if field["status"] == "found":
                    self.assertTrue(field["source_spans"])
                for span in field["source_spans"]:
                    self.assertGreater(span["end"], span["start"])

    def test_frozen_sources_unchanged(self):
        freeze = json.loads((ROOT / "configs/frozen_pilot.json").read_text())
        for name, expected in freeze["source_sha256"].items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), expected, name)

    def test_sample_is_allowed_and_valid(self):
        from app.schemas import ExtractionRun
        run = ExtractionRun.model_validate_json((ROOT / "examples/sample_result.json").read_text())
        self.assertEqual(run.status.value, "completed")
        allowed = json.loads((ROOT / "configs/allowed_pdfs.json").read_text())
        digest = hashlib.sha256((ROOT / "examples/sample_agreement.pdf").read_bytes()).hexdigest()
        self.assertIn(digest, {c["sha256"] for c in allowed["contracts"]})


if __name__ == "__main__":
    unittest.main()
