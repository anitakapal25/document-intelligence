# CUAD field mapping (draft)

CUAD labels text spans. Our JSON values are derived from those spans and must be reviewed before use as reference labels. Keep the original quotation and `answer_start` with each derived value. The supplied text has character offsets but no reliable page number; page stays `null` until PDF parsing supplies provenance.

| CUAD category | Intended JSON value | Review rule |
| --- | --- | --- |
| Document Name | Contract name as a string | Use the annotated name span, not the CUAD `title` identifier. Normalize whitespace and case only for scoring. |
| Parties | List of distinct legal entities | Resolve aliases such as `Company` and `Distributor` to named entities. Merge spelling/suffix variants only after checking context; keep each supporting span. |
| Agreement Date | ISO date `YYYY-MM-DD` | Convert only an unambiguous calendar date. Preserve the original wording as evidence. |
| Effective Date | ISO date `YYYY-MM-DD`, or `null` with a status | Relative or event-based wording can be valid evidence without a fixed date. Mark it `ambiguous` and do not invent a timestamp. |
| Governing Law | Canonical jurisdiction string | Normalize an explicit jurisdiction (for example, `State of Illinois` to `Illinois, US`) using a documented lookup. Do not infer from an address or venue clause. |

Each field carries a status and supporting quotation(s). `is_impossible: true` with `answers: []` indicates no annotated answer for that question, but absence handling still needs care in scoring. A quotation must match the source text; normalized values need not be literal substrings.

Milestone 2 separates field statuses (`found`, `missing`, `ambiguous`, `failed`) from run statuses (`completed`, `partial`, `failed`, `refused`, `incomplete`). Reference labels may also be `unscorable` when a CUAD annotation does not support the intended normalized field. See `TEXT_EXTRACTION.md` and `references/development.json`.

Milestone 4 review found four unannotated but source-supported dates in the development sample. Their reference spans carry `origin: manual_review` and `qa_id: null`, so they cannot be confused with CUAD answers. `EVALUATION.md` documents each override, normalization rules, and the resulting post-run adjudication limit.

## First training contract: manual notes

- Document Name: `DISTRIBUTOR AGREEMENT`; CUAD title is a longer filing identifier.
- Parties: aliases and legal-name variants appear as separate answer spans. Unique entities require review.
- Agreement Date: `7th day of September, 1999.` supports `1999-09-07`.
- Effective Date: two matching clause spans describe immediate effectiveness and an event-based commencement. No fixed calendar date is established by these spans; proposed value `null`, status `ambiguous`.
- Governing Law: the clause names the State of Illinois; proposed normalized value `Illinois, US`.

## Official split check

| File | Contract records | Distinct titles |
| --- | ---: | ---: |
| `data/raw/cuad_benchmark/train_separate_questions.json` | 408 | 408 |
| `data/raw/cuad_benchmark/test.json` | 102 | 102 |

Exact title overlap across the two files: **0**. This is a contract-level identifier check, not a duplicate-text audit. Development contracts must come from the training file; the test file remains reserved for frozen evaluation. Test answers were not examined for this check.

## Second training contract: manual notes

- Document Name: `Promotion and Distribution Agreement`.
- Parties: spans include `Google`, `Google Inc`, `Distributor`, and `Whitesmoke Inc.`. `Google` and `Google Inc` start at the same offset; review aliases and legal names before assigning unique entities.
- Agreement Date: `is_impossible: true`, `answers: []`. Do not derive a date from the CUAD title or substitute the effective date.
- Effective Date: `1 August 2011` supports `2011-08-01`.
- Governing Law: the clause says `English law`; proposed canonical jurisdiction `England and Wales`, subject to the documented normalization policy. The same clause also mentions English courts, but governing law and forum are distinct fields.
- All 27 printed answer spans matched the source text.
