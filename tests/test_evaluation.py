import unittest

from app.evaluation import normalize_jurisdiction, score_field


class EvaluationTests(unittest.TestCase):
    def test_wrong_scalar_counts_fp_and_fn(self):
        reference = {"status": "found", "value": "1999-09-07", "source_spans": []}
        prediction = {"status": "found", "value": "1999-09-08", "evidence": []}
        scored = score_field("Agreement Date", reference, prediction, [""], source_type="cuad_supplied_text")
        self.assertEqual((scored["tp"], scored["fp"], scored["fn"]), (0, 1, 1))

    def test_parties_match_one_to_one(self):
        reference = {"status": "found", "value": ["Acme Ltd", "Beta LLC"], "source_spans": []}
        prediction = {"status": "found", "value": ["Acme Ltd", "Acme Ltd", "Gamma Inc"], "evidence": []}
        scored = score_field("Parties", reference, prediction, [""], source_type="pdf:docling")
        self.assertEqual((scored["tp"], scored["fp"], scored["fn"]), (1, 2, 1))

    def test_missing_and_failure_are_separate(self):
        reference = {"status": "missing", "value": None, "source_spans": []}
        absent = score_field("Agreement Date", reference,
                             {"status": "missing", "value": None, "evidence": []},
                             [""], source_type="cuad_supplied_text")
        failed = score_field("Agreement Date", reference, None, [""], source_type="cuad_supplied_text")
        self.assertEqual(absent["correct_absent"], 1)
        self.assertEqual(failed["correct_absent"], 0)
        self.assertEqual(failed["prediction_status"], "processing_failed")

    def test_jurisdiction_lookup_does_not_guess(self):
        self.assertEqual(normalize_jurisdiction("State of Illinois"), "illinois, us")
        self.assertEqual(normalize_jurisdiction("English law"), "england and wales")
        self.assertEqual(normalize_jurisdiction("laws of the State of New York, U.S.A."), "new york, us")
        self.assertEqual(normalize_jurisdiction("People's Republic of China"), "china (prc)")
        self.assertEqual(normalize_jurisdiction("Federal Republic of Germany"), "germany")
        self.assertIsNone(normalize_jurisdiction("Chicago venue"))

    def test_evidence_span_and_token_scoring(self):
        context = "Agreement governed by Illinois law."
        reference = {"status": "found", "value": "Illinois, US", "source_spans": [
            {"paragraph": 0, "start": 22, "end": 34}]}
        prediction = {"status": "found", "value": "State of Illinois", "evidence": [
            {"quote": "Illinois law", "start": 22, "end": 34, "page": None}]}
        scored = score_field("Governing Law", reference, prediction, [context],
                             source_type="cuad_supplied_text")
        self.assertEqual(scored["tp"], 1)
        self.assertEqual(scored["evidence_token_f1"], 1)
        self.assertEqual(scored["evidence_span_iou"], 1)


if __name__ == "__main__":
    unittest.main()
