# Milestone 7: frozen evaluation and portfolio delivery

Completed locally on 2026-10-18. Cloud deployment remains a separate, unfinished Milestone 6 task pending billing and infrastructure checks.

## What was delivered

- Ten fixed official-test contracts evaluated through supplied text and Docling PDFs, with the original model/prompt/schema/parser/scorer hashes unchanged.
- Derived references reviewed against CUAD annotations and source context before predictions. Review was performed by the agent, not an independent human annotator; two unsupported jurisdictions are explicitly excluded.
- All first attempts retained: 10/10 text runs completed; 9/10 PDF runs completed and the 88-chunk contract hit the 80-chunk limit. No failed contract was silently removed or rerun.
- [Full report](reports/held_out.md), [machine-readable metrics](reports/held_out_metrics.json), [error review](reports/held_out_errors.md), and [evidence audit](reports/held_out_audit.json). Local runs and evaluation records are also saved in DuckDB.
- [README](README.md), architecture diagram, synthetic sample PDF and JSON, [48-second offline walkthrough](examples/pilot_walkthrough.mp4), and [live demo script](DEMO.md).

## Results to explain in an interview

| Field | Supplied-text F1 | Docling PDF F1 |
| --- | ---: | ---: |
| Document name | 0.800 | 0.462 |
| Parties | 0.875 | 0.700 |
| Agreement date | 0.923 | 1.000 |
| Effective date | 1.000 | 0.667 |
| Governing law | 1.000 | 1.000 |

Read these with the report's support and failures. PDF processing failures are excluded from value denominators, and New Jersey/Delaware are unsupported by the frozen scorer. Perfect scores on small supported subsets do not mean universal accuracy. Party alias duplication and page-level title conflicts are the main observed PDF weaknesses. All 267 emitted quotations passed exact source/page-offset verification; factual interpretation can still be wrong.

Recorded known OpenAI usage costs approximately **$0.0571** for the 20 final runs, excluding other provider/cloud fees. Local PDF median wall time was 206 seconds, p95/max 1,216 seconds. The latter exceeds the proposed synchronous cloud timeout; do not present the current serving design as ready for broader production uploads.

## Revision notes

An experiment freeze is like locking a PHP/JS release and test fixtures: changing code after seeing results invalidates the same test as a clean holdout. Reference labels map human annotations to application values; aliases and incomplete dates require explicit rules. Precision/recall measure extracted facts, while quotation validation and evidence overlap answer different questions. The test runner's cached first attempts make interruptions recoverable without cherry-picking successes.

## Checks

```powershell
.\.venv\Scripts\python.exe -m scripts.freeze_pilot --verify-only
.\.venv\Scripts\python.exe scripts\validate_manifests.py
.\.venv\Scripts\python.exe -m scripts.report_held_out
.\.venv\Scripts\python.exe -m scripts.audit_held_out
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Reporting and auditing reuse saved artifacts and make no model calls. The video is a captioned explanatory slideshow using a saved real synthetic extraction, not a live UI screen recording. The report is saved locally for repository/portfolio use; nothing has been published or deployed externally.
