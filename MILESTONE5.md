# Milestone 5: parser comparison and observability

The comparison uses three selected **development** contracts (manifest indices 0, 2, and 4), each processed once by Docling and LlamaParse. Both paths use GPT-6 Luna, prompt `text-v2`, the same Pydantic schema, and the same LlamaIndex chunking and merge code. LlamaParse is pinned to `cost_effective` tier, version `2026-09-28`; Docling is 2.140.0. Parsed pages and run outputs are cached under ignored `outputs/parser_comparison/`. The held-out contracts and labels were not used.

| Metric on these 3 contracts | Docling | LlamaParse |
| --- | ---: | ---: |
| Document Name correct | 1/3 | 2/3 |
| Parties matched entities | 6/6 | 6/6 |
| Agreement Date correct, when found in reference | 1/2 | 2/2 |
| Governing Law correct, when found in reference | 2/2 | 2/2 |
| Parse time, three PDFs | 212.3 s | 43.4 s |
| Extraction time, three PDFs | 67.1 s | 52.5 s |
| OpenAI input/output tokens | 14,905 / 4,933 | 14,995 / 3,831 |
| Estimated OpenAI cost | $0.00396 | $0.00342 |

These denominators are small. One contract has no annotated Parties answer; no contract here has a scorable fixed Effective Date. Processing failures were zero in the six completed runs. The estimate excludes LlamaParse credits, taxes, and other provider charges. Parse time is machine- and network-dependent; Docling startup/model loading accounts for part of this local timing. LlamaParse uploads the PDF to LlamaCloud. The raw score rows, evidence token-overlap results, and exact timings are in `outputs/parser_comparison/comparison.json`.

The Soupman PDF's reference name is a long attachment/addendum/appendix heading; both parsers led the model to a shorter name, so both fail normalized exact match. On the Virgin Galactic PDF, LlamaParse produced the annotated `Joint Filing Statement` and agreement date, while Docling produced an extended title and missed the date. This is a development observation, not evidence that one parser is generally better. The supplied-text baseline also exposed title-scope disagreements, one unrelated event date used as Effective Date, and party-alias issues. We kept the prompt fixed for a fair parser comparison and avoided tuning it to these three documents. Punctuation-only party variants are deduplicated in the shared merge code.

`configs/frozen_pilot.json` records the primary Docling path, comparison LlamaParse path, model/prompt/schema/chunk settings, scoring code, dependency versions, and source/manifest hashes. Run `python -m scripts.freeze_pilot` before held-out evaluation; it fails if these tested inputs have changed. A change requires a new development experiment and a new freeze. The held-out benchmark remains pending.

Phoenix tracing is optional: `app/tracing.py` registers `arize-phoenix-otel` only when `PHOENIX_COLLECTOR_ENDPOINT` is set. It uses manual spans with an allowlist of parser, PDF hash, page/chunk counts, status, token counts, and elapsed time; it does not instrument OpenAI requests or record document text, prompts, quotations, filenames, or model output. The privacy regression test checks this attribute boundary. Phoenix 20.23.0 was started from `.venv`; `/healthz` returned 200, the OTLP collector accepted the connection-check span, and `scripts.verify_phoenix` confirmed the span was persisted locally.

To start Phoenix locally in `.venv`, run this in one PowerShell terminal:

```powershell
$env:PHOENIX_WORKING_DIR = (Join-Path (Get-Location) 'outputs\phoenix')
$env:PHOENIX_HOST = '127.0.0.1'
$env:PYTHONIOENCODING = 'utf-8'
.\.venv\Scripts\phoenix.exe serve
```

In a second PowerShell terminal, run:

```powershell
$env:PHOENIX_WORKING_DIR = (Join-Path (Get-Location) 'outputs\phoenix')
$env:PHOENIX_COLLECTOR_ENDPOINT = 'http://127.0.0.1:6006/v1/traces'
$env:PYTHONIOENCODING = 'utf-8'
.\.venv\Scripts\python.exe -m scripts.check_phoenix
.\.venv\Scripts\python.exe -m scripts.verify_phoenix
```

Open `http://127.0.0.1:6006` to inspect traces. Because the comparison runs are cached, rerunning it will not emit new extraction spans; `scripts.check_phoenix` sends a safe connection-check span instead. Phoenix persists to ignored `outputs/phoenix/`. Docker is optional; `compose.phoenix.yaml` remains available if you later prefer a container. The endpoint follows the [Phoenix tracing endpoint](https://arize.com/docs/phoenix/learn/faqs/what-is-my-phoenix-endpoint) documentation. Keep this unauthenticated local service bound to `127.0.0.1`.

Python comparison: `with metadata_span(...):` is like a JS `try/finally` wrapper or PHP middleware around one operation. The span captures timing and approved metadata. The parser adapters implement the same interface, similar to two PHP classes implementing one interface; the extractor sees `ParsedDocument` either way.
