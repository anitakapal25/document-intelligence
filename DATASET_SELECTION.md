# CUAD pilot sample

The tracked manifests in `manifests/` contain contract identifiers and normalized-text SHA-256 fingerprints, not contract text or test labels. Generate them with `scripts/build_manifests.py`; check them with `scripts/validate_manifests.py`. The source JSON files under `data/raw/` remain ignored by Git.

## Selection rules

- Official source: `train_separate_questions.json` (408 contracts) for development and `test.json` (102 contracts) for held-out testing.
- Fixed random seed: `42`.
- Development sample: retain the first two manually inspected contracts and the sole training contract without a Parties annotation. Ensure at least 3 absent Agreement Date, 4 absent Effective Date, and 3 absent Governing Law cases; fill to 20 by seeded random selection. This intentionally enriched sample is not representative of CUAD's natural field prevalence.
- Held-out sample: choose 10 titles by seeded random selection from the official test split, excluding any exact normalized-text match to a selected development contract. Test answers and field coverage are not used in selection.
- A fingerprint is SHA-256 of the contract context with whitespace collapsed and case folded. The validator checks title membership, within-sample uniqueness, current source fingerprints, and cross-sample title/text overlap.

## Audit findings

- The complete official training split has 407 distinct normalized-text fingerprints among 408 titles. Two ADUROBIOTECH consulting agreement titles share the same text. The complete test split has 102 distinct fingerprints. Cross-split normalized-text overlap is zero.
- Selected development coverage: Document Name 20/20; Parties 19/20; Agreement Date 15/20; Effective Date 12/20; Governing Law 16/20. Coverage means an annotated span exists, not that a normalized value can be assigned.
- The held-out manifest contains no test coverage counts. Reference labels will be reviewed only after model, prompt, schema, parser, and scorer settings are frozen.
- Results from 20 development and 10 held-out contracts will be presented as a pilot benchmark with support counts, not as production-wide accuracy.
