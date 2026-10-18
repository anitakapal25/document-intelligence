# Milestone 2: extraction from CUAD-supplied text

The first extraction path reads the official CUAD training JSON. This isolates model extraction from later PDF parsing. It processes one development contract at a time; no benchmark batch is triggered by the CLI.

## Reference labels

`scripts/review_development.py` displays the five categories for each selected contract and verifies CUAD's character offsets. `scripts/build_dev_references.py` writes `references/development.json` for the 20 development contracts. Each reference field keeps source spans and a reviewed status/value. After Milestone 4 adjudication, the reference file has 76 found, 14 missing, 9 ambiguous, and 1 unscorable field. Four dates omitted by CUAD have manually derived spans marked `manual_review`. The unscorable Governing Law annotation is actually about arbitration locations. Redacted and blank dates remain ambiguous. These are development judgments, not production ground truth; see `EVALUATION.md`.

## Result shape

Each field contains `status`, `value`, `evidence`, and `issue`. Scalar values are strings or `null`; Parties is a list of distinct names. Found dates must be real ISO calendar dates. An evidence item records the exact quotation and source character offsets. `page` is `null` for CUAD-supplied text because this source has no page provenance. The top-level run status distinguishes completed, partial, failed, refused, and incomplete runs. Metadata records model, prompt version, elapsed time, response ID, and available token usage.

The OpenAI response is parsed against a strict Pydantic schema. Application checks then require every quotation to occur exactly in the source text and enforce the field's value/status rules. A failed evidence check marks that field `failed` and the run `partial`; it does not silently accept the unsupported quotation. Structured Outputs guarantees the response shape, not factual correctness.

## Run locally

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m scripts.extract_cuad --index 0 --dry-run
```

For a live call, copy `.env.example` to the Git-ignored `.env` file and replace the placeholder with your key, or set `OPENAI_API_KEY` in the local environment. Then omit `--dry-run`. The program uses GPT-6 Luna, submits the CUAD text with `store=False`, and writes its result under ignored `outputs/text_runs/`. It reuses completed cached runs for identical model, prompt, and text. Do not put a key in source code or commit it.

```powershell
Copy-Item .env.example .env
# Open .env in VS Code and replace the placeholder without sharing it in chat.
.\.venv\Scripts\python.exe -m scripts.extract_cuad --index 0
```

The script rejects empty input and text over 200,000 characters instead of silently truncating it. Day 3 adds chunking for larger documents. API timeouts, connection errors, rate limits, and server errors receive at most two retries. Refusal, incomplete output, and schema errors are reported explicitly.

The first live call on development contract 0 returned a structured, `partial` result: three fields had unsupported quotations. Prompt version `text-v2` requests shorter copied quotations. The evidence validator now tolerates whitespace-only differences in CUAD's line-wrapped text and records the actual source substring and offsets. It still rejects changed words or punctuation. A repeat live call returned `completed`: Document Name, Parties, Agreement Date, and Governing Law were found, and Effective Date was ambiguous. All stored evidence mapped to the source; pages remain `null`. The repeat used 10,597 input and 603 output tokens and recorded 8,896 ms. This is one verified example, not a quality benchmark.

OpenAI's [Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses) documents the `responses.parse` Pydantic helper used here.
