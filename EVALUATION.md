# Milestone 4: local development evaluation

Run `python -m scripts.run_development_text` from the project virtual environment to process all 20 selected training contracts. It reuses completed `text-v2` cache entries and stops at a conservative $1 estimated new-call threshold. Then run:

```powershell
.\.venv\Scripts\python.exe -m scripts.evaluate_runs --all-development-text --run "outputs\pdf_runs\LIMEENERGYCO_09_09_1999-EX-10-DISTRIBUTOR AGREEMENT_docling.json"
.\.venv\Scripts\python.exe -m scripts.analyze_errors
```

The report is `outputs/reports/development_baseline.md`; DuckDB is `data/processed/benchmark.duckdb`. Both are local, Git-ignored artifacts. DuckDB has `runs`, `predictions`, and `evaluations` tables keyed by a hash of the saved run JSON. Runs record status, model, prompt, source, tokens, recorded model-call latency, and estimated OpenAI cost. Predictions store values and evidence. Evaluations store reference/prediction statuses and per-field counts. The report compares 20 CUAD supplied-text runs and one Docling PDF run of the same selected contract. It does not include held-out test data.

## Value scoring policy

| Field type | Rule |
| --- | --- |
| Document name | Exact match after case folding and whitespace collapsing. Different titles count FP + FN. |
| Parties | Normalize case and remove punctuation, then match one-to-one as a multiset. An extra entity is FP; an unmatched reference entity is FN. |
| Dates | Compare real ISO `YYYY-MM-DD` dates only. References without a fixed calendar date are ambiguous and excluded from value precision/recall. |
| Governing law | Apply the explicit lookup in `app/evaluation.py`: named US states map to `<state>, US`; English law to England and Wales; PRC/China, Germany, and Israel have listed aliases. Unrecognized wording does not get a guessed jurisdiction. |

For scorable references, wrong scalar replacements count as FP and FN. A missing reference with a missing prediction is `correct_absent` and does not inflate precision/recall. Found predictions on missing references count as false present; ambiguous predictions are recorded as abstentions. A failed field or run is counted separately as a processing/schema failure, not converted to a missing prediction. Reference statuses `ambiguous` and `unscorable` are excluded from value denominators and reported with support counts.

Evidence is scored separately. Token F1 uses the best pair between a CUAD reference span and a predicted quotation. Character-span intersection-over-union is calculated only for CUAD supplied text, where offsets share a source. PDF parser page-relative offsets cannot be compared directly with CUAD text offsets. The report gives evidence support and scored-pair counts; evidence with no predicted quotation is not silently assigned a zero overlap.

## Reference adjudication and observed errors

The first reference pass derived values from CUAD annotations. During development error review, four CUAD-omitted date fields were manually added with exact source spans marked `origin: manual_review`: Slovak Wireless Agreement Date (the contract states `dated 10 October 2000`), and Effective Date for Integrity Funds, Ultragenyx, and Sibannac (each has a date plus execution/effectiveness language). The Reynolds `Commencement Date` describes an IPO transition, not clearly this agreement's effective date, so its reference remains missing. These are review decisions made after viewing predictions; the development scores are exploratory and should not be presented as unbiased test results.

The main remaining name errors choose a broader agreement title where CUAD annotates a particular addendum or amendment, or include extra title wording. The remaining Effective Date false positive is the Reynolds IPO commencement. One Usio run is `partial`: its Agreement Date and Effective Date fields failed source-quotation validation. The first saved Docling result includes an `LLC`/`L.L.C.` duplicate party; punctuation-insensitive deduplication was added afterward and verified by a unit test, but the saved run remains a faithful record of its original output. The small PDF sample cannot support a parser-quality claim.

The cost estimate uses [OpenAI's published GPT-6 Luna standard short-context rates](https://developers.openai.com/api/docs/models/gpt-6-luna) of $0.10 per million input tokens and $0.50 per million output tokens. It is an estimate from recorded token totals, excludes cached-input discounts and parser fees, and is not a billing statement. Model-call latency excludes PDF parsing, upload, and total request time; end-to-end instrumentation is still needed for serving decisions.
