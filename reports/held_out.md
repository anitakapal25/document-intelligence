# Frozen held-out pilot report

Ten contracts selected with seed 42 from CUAD's official 102-contract test split; 20 training contracts were used for development. Selected title and normalized-text overlap checks passed. This is a small portfolio pilot, not a production accuracy estimate.

Model, prompt, schema, parsers, chunking, scorer, and manifests were frozen before test labels were opened. Reference values were agent-reviewed against answer spans and surrounding source text before predictions; this is not independent human adjudication. References and protocol hashes are recorded in `reports/held_out_metrics.json`. No tuning or selective reruns followed test results.

Aliases and former names were consolidated to entities. Original CUAD title extent and OCR spellings were retained. Missing means no CUAD answer annotation, not proof of absence in the complete document. Blank/year-only dates and conditional dates without a definite calendar date were marked ambiguous. New Jersey and Delaware are outside the frozen jurisdiction lookup: two governing-law labels are explicitly unscorable, with their actual values retained in the reference file.

Wrong replacements count FP + FN. Ambiguous/unscorable references are excluded from value scores. Processing failures are reported separately and excluded from value denominators, so read F1 together with failure counts and support. A completed run means processing succeeded, not that extracted facts are correct.

Evidence token F1 uses the best reference/prediction quotation pair; it is not a measure of complete evidence coverage. Missing quotations are reported through reference support versus scored-pair counts. Span IoU applies only to supplied text; PDF page-relative offsets have no direct CUAD alignment.

Reference positive support: 10 document names, 24 party entities across 10 contracts, 7 agreement dates, 4 effective dates, and 7 supported governing-law values. Two additional jurisdictions are excluded by the frozen normalizer. Agreement dates have 1 absent and 2 ambiguous labels; effective dates have 3 absent and 3 ambiguous labels; governing law has 1 absent label.

## cuad_supplied_text (10 contract run(s))

| Type | Field | Ref found | Ref missing | Ambig./excluded | TP | FP | FN | Precision | Recall | F1 | Correct absent | False present | Absent abstained | Failures | Evidence ref support | Evidence token F1 (n) | Span IoU (n) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| name | Document Name | 10 | 0 | 0 | 8 | 2 | 2 | 0.800 | 0.800 | 0.800 | 0 | 0 | 0 | 0 | 10 | 0.901 (10) | 0.298 (10) |
| entity set | Parties | 10 | 0 | 0 | 21 | 3 | 3 | 0.875 | 0.875 | 0.875 | 0 | 0 | 0 | 0 | 10 | 0.746 (10) | 0.617 (10) |
| date | Agreement Date | 7 | 1 | 2 | 6 | 0 | 1 | 1.000 | 0.857 | 0.923 | 1 | 0 | 0 | 0 | 9 | 0.569 (8) | 0.356 (8) |
| date | Effective Date | 4 | 3 | 3 | 4 | 0 | 0 | 1.000 | 1.000 | 1.000 | 0 | 0 | 3 | 0 | 7 | 0.667 (7) | 0.374 (7) |
| jurisdiction | Governing Law | 7 | 1 | 2 | 7 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1 | 0 | 0 | 0 | 9 | 0.728 (9) | 0.636 (9) |

Run statuses: completed 10. Usage: 114,505 input / 7,589 output tokens. Recorded model-call time: 143.31s. Per-run median/p95: 9.80s/50.10s. Estimated OpenAI cost: $0.01525 (10/10 priced runs).

Observed wall time: median 9.8s, nearest-rank p95 50.1s; includes parse/extraction for PDFs. Total parse time 0.0s. Times describe this local machine, not Cloud Run performance.

## pdf:docling (10 contract run(s))

| Type | Field | Ref found | Ref missing | Ambig./excluded | TP | FP | FN | Precision | Recall | F1 | Correct absent | False present | Absent abstained | Failures | Evidence ref support | Evidence token F1 (n) | Span IoU (n) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| name | Document Name | 10 | 0 | 0 | 3 | 1 | 6 | 0.750 | 0.333 | 0.462 | 0 | 0 | 0 | 1 | 10 | 0.991 (9) | n/a (0) |
| entity set | Parties | 10 | 0 | 0 | 21 | 17 | 1 | 0.553 | 0.955 | 0.700 | 0 | 0 | 0 | 1 | 10 | 1.000 (9) | n/a (0) |
| date | Agreement Date | 7 | 1 | 2 | 6 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1 | 0 | 0 | 1 | 9 | 0.625 (8) | n/a (0) |
| date | Effective Date | 4 | 3 | 3 | 2 | 1 | 1 | 0.667 | 0.667 | 0.667 | 0 | 1 | 2 | 1 | 7 | 0.689 (6) | n/a (0) |
| jurisdiction | Governing Law | 7 | 1 | 2 | 6 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1 | 0 | 0 | 1 | 9 | 0.616 (8) | n/a (0) |

Run statuses: completed 9, failed 1. Usage: 151,949 input / 53,310 output tokens. Recorded model-call time: 709.53s. Per-run median/p95: 56.56s/155.31s. Estimated OpenAI cost: $0.04185 (9/10 priced runs).

Observed wall time: median 206.3s, nearest-rank p95 1216.3s; includes parse/extraction for PDFs. Total parse time 2157.5s. Times describe this local machine, not Cloud Run performance.

## Controlled parser comparison (development only)

Three identical development PDFs were processed by Docling and LlamaParse with the same model, prompt, schema and chunk settings. This comparison was completed before the freeze; LlamaParse was not rerun on the held-out sample.

| Parser | Contracts | Parse seconds | Extraction seconds | Estimated OpenAI USD |
| --- | ---: | ---: | ---: | ---: |
| docling | 3 | 212.3 | 67.1 | 0.00396 |
| llamaparse | 3 | 43.4 | 52.5 | 0.00342 |

Development value counts: Docling matched 1/3 names and 1/2 scorable agreement dates; LlamaParse matched 2/3 and 2/2. Both matched 6/6 parties and 2/2 governing-law values. Effective dates had no scorable fixed-date positives. This sample cannot establish a general parser winner.

## Error analysis and future work

The supplied-text errors concentrate in the OCR-corrupted PrimeEnergy contract and the extent of the STW title/entity names. Exact matching penalizes OCR correction and added suffixes, so not every mismatch is a factual extraction error. The frozen references are left unchanged.

On PDFs, short aliases such as Integra, Fleet, Vapotherm and COFS survive punctuation-only entity deduplication. Several contracts yield conflicting titles from different pages or exhibits, so the scalar merger returns ambiguous. The 88-page Pacira contract exceeds 80 chunks and fails before any model call. It remains in the ten-contract support and failure counts. The Photronics effective-date prediction is false-present against an absent CUAD annotation, which is an annotation disagreement rather than proof that the date is factually wrong.

Future development experiments should evaluate document-level alias resolution, main-agreement versus exhibit scope, and explicit long-document routing. These changes were not made for this test. Broader jurisdiction support and independent reference adjudication should precede stronger quality claims.

## Limits and deployment status

Costs use the frozen estimate of $0.10/M input and $0.50/M output tokens. They exclude provider charges for failed attempts with unavailable usage, LlamaParse fees, cloud charges, discounts, and tax. Known token costs are not a billing statement. The runner conservatively reserves for unknown usage and bounded retries against the $20 project allowance.

Long documents can exceed the 200,000-character supplied-text limit or 80-chunk PDF limit. Cross-page title/date conflicts can produce ambiguous values; entity alias matching is deliberately strict. OCR spelling errors can penalize otherwise corrected PDF values. These are observed or designed pilot limitations, not reasons to remove contracts from the report. The frozen model identifier is a provider model name rather than an immutable weight snapshot; later reruns may differ even with the same files.

Local PDF wall time reached 1,216 seconds (over 20 minutes), exceeding the proposed 900-second synchronous service timeout. These uncontrolled local timings include first-use model loading/download effects and are not hosted latency measurements. OCR model weights were not content-hashed at the original freeze, which limits exact parser reproducibility.

FastAPI and the upload UI are verified locally. Docker build, shared Firestore ledger, private Cloud Run deployment, and cloud upload latency remain unverified pending infrastructure/billing. The deployed upload flow is not claimed complete. The current synchronous configuration is unsuitable for the observed broader PDF workload: add durable asynchronous jobs before claiming that workload supported in the cloud, or independently validate a narrower bounded input scope on the hosted service.
