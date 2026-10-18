# Document Intelligence Pipeline — Revision Log

Keep entries brief. Add each completed step after reviewing the code or output.

## Goal and approach

- Extract document name, parties, agreement date, effective date, and governing law from CUAD contracts, with validated evidence.
- Start with supplied text; add PDF parsing later to separate extraction errors from parsing errors.
- Build in small steps: implement, run, review, then continue.

## Day 1 — Setup and Python foundations

### 1. Check local tools — verified
- Workspace: `C:\Users\Anita\Documents\AI\document-intelligence`.
- Python: `3.14.4`; use `python` because the `py` launcher did not find it.
- Git: `2.41.0`; Docker CLI: `25.0.3` (engine not checked).
- Check AI/parser dependency compatibility before installing packages.

### 2. Create virtual environment — verified
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip --version
```
- `.venv` isolates project packages; pip `26.0.1` points inside it.
- Run its interpreter directly; activation and execution-policy changes are unnecessary.
- Keep application code outside `.venv`; the environment can be recreated.
- VS Code interpreter selection was instructed but not independently verified.

### 3. Save a synthetic contract as JSON — verified
- File: `scripts/create_sample.py`.
- `dict` ≈ JS object / PHP associative array; `None` ≈ `null`.
- `def` declares functions; indentation defines their bodies; type hints describe expected types.
- `Path(__file__).resolve().parent.parent` finds the project root.
- `Path / "folder"` joins paths; `mkdir(parents=True, exist_ok=True)` creates missing folders.
- `with` closes the file automatically; `json.dump` writes UTF-8 JSON with indentation.
- The `__name__ == "__main__"` guard calls `main()` when executed directly.
```powershell
.\.venv\Scripts\python.exe scripts\create_sample.py
```
- Result: `outputs/sample_contract.json`; Python `None` becomes JSON `null`.

### 4. Practice lists, loops, and missing values — verified
- Added a third party; `len(contract["parties"])` returns `3`.
- `for party in contract["parties"]` ≈ JS `for...of` / PHP `foreach`.
- `if contract["effective_date"] is None` checks a missing date.
- Run confirmed all three names and `Effective date is missing`.

### 5. Protect files and create project structure — verified
- Added `.gitignore` for environments, secrets, caches, data, and outputs; `.env.example` remains allowed.
- Created `app/__init__.py`, `tests/`, `data/raw/`, and `data/processed/`; initialized Git.
- Agent Git checks require a command-scoped `safe.directory` because the sandbox user differs from the folder owner; no global setting changed.

## Next steps — pending

- Inspect more CUAD categories and missing answers before defining schemas or scoring.
- Build contract-level development/test manifests with field coverage and leakage checks.

### 6. Inspect a CUAD training record — verified
- Downloaded the official archive to `data/raw/`; inspected `train_separate_questions.json` with `scripts/inspect_cuad.py`.
- Training file contains 408 contract records. First record has one 54,290-character context and 68 question/answer entries.
- `title` is a dataset identifier; the `Document Name` answer is a span of contract text.
- `answer_start` is a character offset into `context`; the five sampled spans matched exactly.
- `Parties` spans include aliases (`Company`, `Distributor`) and legal-name variants. Derive unique normalized parties only after manual review; raw spans are evidence, not ready-made entity labels.
- Keep `test.json` reserved for held-out evaluation.

### 7. Inspect target-field spans and missing answers — verified
- Agreement Date span: `7th day of September, 1999.`; it matches the source and appears unambiguous.
- Effective Date has two matching clause spans, but neither supplies a fixed calendar date. Record the evidence; do not force an ISO date label.
- Governing Law span names the State of Illinois and matches the source.
- `is_impossible: True` occurs for absent categories with `answers: []` in this record; absence still needs cautious interpretation in evaluation.
- A source span may support a field without providing a normalized value; never infer a fixed date from a relative or event-based effective-date clause.
- Use ISO `YYYY-MM-DD` for unambiguous calendar dates. Use a timestamp only when the source gives a time and timezone.

### 8. Draft field mapping and verify official splits — verified
- `FIELD_MAPPING.md` records the five CUAD-to-JSON mappings and cases needing manual review.
- Training: 408 distinct contracts. Test: 102 distinct contracts. Exact title overlap: 0.
- The split check used contract titles and counts; test answers remain reserved for final evaluation.

### 9. Compare two training contracts — verified
- First: agreement date `1999-09-07`; effective date has event-based clauses without a fixed date; governing law Illinois.
- Second: agreement date has no annotated answer; effective date `2011-08-01`; governing law English law.
- Both have multiple party spans representing aliases or name variants. First record: 46 matching spans; second: 27 matching spans; zero mismatches.
- A date embedded in a CUAD title is metadata, not evidence for a missing Agreement Date label.

### 10. Count target-field coverage in training contracts — verified
- `scripts/check_coverage.py` counts each field once per contract, even when it has multiple answer spans.
- Of 408 training contracts: Document Name 408 present / 0 absent; Parties 407 / 1; Agreement Date 377 / 31; Effective Date 320 / 88; Governing Law 354 / 54.
- Effective Date has the most absent annotations. The development sample should include both present and absent examples for every field where possible.
- Presence of an annotated span does not guarantee a normalized value (for example, an event-based effective date).

### 11. Export contract-level coverage — verified
- `scripts/check_coverage.py` writes `data/processed/train_coverage.csv` with one row per training contract and five presence flags.
- Verified 408 rows, 408 distinct titles, and unchanged aggregate counts.
- This table supports deliberate development-sample selection; it does not contain normalized reference values.

### 12. Locate rare missing-field cases — verified
- The sole training contract without an annotated Parties answer is `SoupmanInc_20150814_8-K_EX-10.1_9230148_EX-10.1_Franchise Agreement3`; it also lacks Agreement Date and Effective Date answers, while Governing Law is annotated.
- Training examples with missing Governing Law, Agreement Date, and Effective Date were identified from the coverage CSV for development sampling.
- Missing annotation means no CUAD answer for that field; selected cases still need source review before reference labels are finalized.

### 13. Build and validate pilot manifests — verified
- `scripts/build_manifests.py` selected 20 development contracts from the official training split and 10 held-out contracts from the official test split with seed 42.
- `scripts/validate_manifests.py` checks source membership, unique titles/text, fingerprints, and zero selected cross-split overlap. Test answers were not used for selection.
- Development coverage: Document Name 20/20, Parties 19/20, Agreement Date 15/20, Effective Date 12/20, Governing Law 16/20.
- Full training split has one normalized-text duplicate pair; the selected samples contain no duplicate text. `DATASET_SELECTION.md` records the rules and limits.

### 14. Review development references — first pass complete
- `references/development.json` contains manually normalized values for the 20 selected training contracts, with original CUAD span offsets.
- 72 fields found, 18 missing, 9 ambiguous, 1 unscorable. A CUAD Governing Law label that only identifies arbitration locations is excluded from value scoring.
- Redacted or blank dates remain ambiguous; event-based effective dates do not get invented calendar values.

### 15. Extract from supplied text — offline checks verified
- Installed OpenAI SDK 2.54.0 and Pydantic 2.14.1 in `.venv`; versions recorded in `requirements.txt`.
- `app/schemas.py` defines the structured response and run metadata. `app/evidence.py` checks quotations, statuses, unique parties, and real ISO dates.
- `app/extractor.py` uses the Responses API with GPT-6 Luna, bounded retries, and explicit failed/refused/incomplete statuses. The CLI processes one manifest-selected contract and caches completed runs.
- Local unit tests and dry runs pass. A live GPT-6 Luna extraction of development contract 0 completed with a structured response (10,569 input tokens, 547 output tokens, 8,524 ms). Document Name and Agreement Date passed exact-source evidence checks. Parties, Effective Date, and Governing Law returned unsupported quotations and were marked `failed`, so the run is `partial`. This is a useful real error-analysis case; do not treat schema compliance as extraction accuracy.

### 16. Resolve live evidence failures — verified
- Prompt version `text-v2` requests short copied quotations. The evidence validator accepts whitespace-only differences caused by CUAD line wrapping, then stores the exact source substring and offsets. Changed words or punctuation still fail.
- Repeating development contract 0 produced a `completed` run: Document Name, Parties, Agreement Date, and Governing Law were found; Effective Date was correctly marked ambiguous because the clauses do not establish a fixed calendar date. All evidence spans passed source checks, with no invented pages.
- The live run used 10,597 input and 603 output tokens and recorded 8,896 ms. Ten local unit tests pass. This verifies the extraction path on one contract, not benchmark accuracy across the development set.

### 17. Add PDF parsing and page-aware chunks — verified locally
- Installed Docling 2.140.0, LlamaIndex core 0.14.25, and current LlamaCloud 2.18.0. `pip check` and 11 unit tests pass.
- Downloaded all 20 selected development PDFs from the Atticus Project's CUAD mirror by exact filename. The first real contract parsed into 10 pages and 10 chunks. Held-out PDFs were not opened.
- A synthetic two-page PDF passed end-to-end extraction. Evidence quotations have parser page numbers and page-relative offsets; supplied CUAD text still has no page numbers. LlamaIndex preserves page metadata while splitting.
- The LlamaParse adapter uses LlamaCloud's current page-level Markdown API. A live comparison awaits a LlamaCloud key. See `PDF_PIPELINE.md` for commands and limitations.
- A full Docling + GPT-6 Luna run on the first selected real PDF completed with page-backed evidence. The first-pass merger duplicated an `LLC`/`L.L.C.` party variant; punctuation-insensitive deduplication is now covered by a regression test. Thirteen unit tests pass. The saved run predates that fix.
- LlamaParse then passed a live two-page synthetic PDF parse and full extraction. With model, prompt, and schema fixed, its five values/statuses and evidence pages matched the Docling synthetic run. A real-contract parser comparison remains for Milestone 5.

### 18. Evaluate the development baseline — verified
- Ran the 20 selected CUAD training contracts through the cached `text-v2` extractor. One run was partial because two quotations failed validation. The held-out split remains untouched.
- Added field-type precision/recall/F1 and support counts, separate absent-answer outcomes, evidence token F1 and text-only span IoU, plus DuckDB run/prediction/evaluation tables. A one-contract Docling result is shown separately.
- Manually reviewed disagreements and added four CUAD-omitted date references with source spans marked `manual_review`. Development scores include this post-run adjudication and are exploratory. See `EVALUATION.md` and ignored `outputs/reports/development_baseline.md`.
- Recorded GPT-6 Luna token usage, model-call latency, and an estimated OpenAI cost using current published rates. Parser time and LlamaParse cost are not included in that estimate.

### 19. Compare parsers and freeze the pilot — verified
- Ran the same three development PDFs through Docling and LlamaParse with unchanged GPT-6 Luna prompt, schema, chunking, and scorer. All six extractions completed; no held-out document was used.
- LlamaParse matched 2/3 document names and 2/2 scorable agreement dates; Docling matched 1/3 and 1/2. Both matched 6/6 annotated parties and 2/2 governing-law values. This tiny sample does not establish a general winner.
- Recorded parse time, extraction time, tokens, estimated OpenAI cost, and field/evidence scores in ignored `outputs/parser_comparison/comparison.json`. LlamaParse charges are not included in the OpenAI estimate.
- Added optional Phoenix metadata-only spans and a privacy regression test. Started Phoenix from `.venv` with storage in ignored `outputs/phoenix/`; health check returned 200 and a test span was persisted. Docker is optional.
- `configs/frozen_pilot.json` hashes the tested model, prompt, schema, parsers, scorer, and manifests before the held-out phase. See `MILESTONE5.md` for results and commands.

### 20. Add the private upload API — local checks verified
- Added FastAPI `GET /health`, `POST /extract`, and a small upload/download page. The API accepts only exact listed CUAD/synthetic PDFs up to 10 MiB, uses frozen Docling extraction, and removes temporary uploads after each request.
- A real synthetic-PDF upload returned HTTP 200 with all five fields, statuses, and correct page-backed evidence. Contract tests cover invalid type/size/scope, parser failure, refusal, missing fields, and budget limit.
- Added a local in-memory estimated-cost guard and transactional Firestore backend for shared Cloud Run usage. The cloud ledger is not live-tested yet.
- Deployment follow-up (2026-10-18): confirmed project `tidal-anvil-286512`; active billing needs owner verification because the linked account redirects to signup. Cloud Shell remained blank. Added a runtime-only `.gcloudignore` upload allowlist and redacted exception logs. All 27 tests pass and `python -m scripts.freeze_pilot` confirms the existing freeze. Cloud deployment remains pending.
- Added runtime Dockerfile, `.dockerignore`, pinned runtime dependencies, and a guarded Cloud Run deploy script. Docker Desktop's engine was unavailable and `gcloud` was not installed, so container build and private cloud deployment remain pending. See `MILESTONE6.md`.

### 21. Finish the frozen held-out pilot and portfolio
- Verified the freeze and split separation; reviewed the ten held-out references before predictions. Two jurisdictions are outside the frozen scorer; incomplete dates remain ambiguous. Review is agent-led, not independent human adjudication.
- Saved all first attempts: 10 completed text runs; 9 completed PDF runs and one 88-chunk/80-limit failure. No test-driven tuning or selective reruns.
- Generated field/evidence metrics, failure and absent-answer counts, latency/cost, parser-comparison summary, error review, and local DuckDB records. All 20 run schemas and 267 quotations passed the final source audit.
- Added README/architecture, sample PDF/JSON, live demo guide, and a 48-second captioned offline MP4. See `MILESTONE7.md` and `reports/held_out.md`.
- Thirty tests and dependency checks pass. Known final-run OpenAI cost is about $0.0571. A local PDF took over 20 minutes: async jobs or a separately validated narrower input scope are needed before claiming cloud readiness. Billing/deployment remain deferred.

### 22. Publish the portfolio repository
- Created public repository https://github.com/anitakapal25/document-intelligence and pushed the project to `main`, preserving the initial learning commit.
- Audited publication candidates and existing Git history for key material; excluded `.env`, virtual environments, raw datasets, and local outputs. Included code, reviewed references, aggregate reports, synthetic examples, and the demo.
- Added `.gitattributes` to preserve exact file bytes across clones so the frozen experiment hashes remain valid. GitHub publication hosts the source; the running Cloud Run application is still not deployed.
- Expanded `.gitignore` for local caches, coverage/build output, database files, logs, temporary/editor files, and conventional credential files. Kept benchmark manifests/references, reports, and synthetic demo artifacts tracked; no existing tracked file required removal.

### 23. Prepare a narrow cloud demo
- Chose four exact PDFs for the first synchronous deployment: three development comparison PDFs plus the synthetic example. `PILOT_SCOPE=demo` selects their SHA-256 allowlist; the larger local development list remains available.
- Added an accepted-document list and synthetic sample download to the upload page. Unknown scope settings fail closed.
- All 32 tests pass; frozen extraction source hashes remain unchanged. Cloud validation is pending and must cover every accepted demo PDF before declaring the upload flow ready.
- Confirmed active Google Cloud billing, enabled deployment APIs, and created a dedicated runtime identity and default Firestore Native database in Mumbai. The user created the OpenAI secret in Secret Manager.
