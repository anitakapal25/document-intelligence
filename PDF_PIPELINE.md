# Milestone 3: PDF parsing and page provenance

`app/parsers.py` exposes two parser adapters with the same `ParsedDocument` shape: one-based pages containing parser text. Docling 2.140.0 is the local primary parser. LlamaCloud 2.18.0 supplies the optional LlamaParse comparison adapter; it needs `LLAMA_CLOUD_API_KEY` and uploads the PDF to LlamaCloud. The current adapter requests the `cost_effective` tier and page-level Markdown. A failed page causes an error instead of a fabricated page number.

`app/pdf_workflow.py` converts each page to a LlamaIndex `Document`, splits it with `SentenceSplitter`, and carries page metadata into every chunk. Each chunk uses the same GPT-6 Luna prompt and Pydantic response as Milestone 2. Evidence is validated against the chunk, then located again in its full parser page. Offsets in PDF output are **page-relative**, unlike CUAD supplied-text offsets. Chunk values are combined; conflicting scalar values become ambiguous, while duplicate party names are collapsed case-insensitively. This is a first-pass merge rule for pilot error analysis, not a final quality claim. Documents over 80 chunks fail explicitly instead of being silently truncated.

The original PDF files for all 20 development contracts were matched by exact filename in the [Atticus Project CUAD mirror](https://huggingface.co/datasets/theatticusproject/cuad/tree/main/CUAD_v1/full_contract_pdf) and saved under ignored `data/raw/cuad_pdfs/development/`. Held-out PDFs and labels were not used. The original PDF text can differ from CUAD's supplied training text; evaluation must treat parsing differences separately.

Run the smoke tests from the project root:

```powershell
.\.venv\Scripts\python.exe -m scripts.create_synthetic_pdf
.\.venv\Scripts\python.exe -m scripts.extract_pdf data\synthetic\sample_agreement.pdf --parse-only
.\.venv\Scripts\python.exe -m scripts.extract_pdf data\synthetic\sample_agreement.pdf
```

The synthetic two-page PDF parsed into two page chunks. A live extraction returned `completed`: document name, parties, and agreement date on page 1; ambiguous effective date and found governing law on page 2. Every quotation matched its parser page. The two model calls used 1,134 input and 512 output tokens, with 14,304 ms combined model time. Docling parsed the first selected real CUAD PDF into 10 pages and 10 chunks. Its live extraction also returned `completed`, with page-backed evidence for all five fields (effective date ambiguous), using 12,929 input and 3,761 output tokens and 59,887 ms combined model time. That saved first-pass result includes one duplicate party spelling (`LLC`/`L.L.C.`); the merge rule was then improved and tested without another paid run. Parser time is not yet included in run metadata; Day 4 adds end-to-end latency measurement and analytics.

The LlamaParse adapter was live-tested with a key from the Git-ignored `.env` file. It returned two pages and two chunks for the synthetic PDF. Using the same GPT-6 Luna model, prompt, and schema, the LlamaParse path also returned `completed` and the same five field values/statuses and evidence pages as Docling. It used 1,137 input and 539 output tokens. This checks adapter wiring on a simple synthetic PDF; the controlled comparison on matched CUAD PDFs belongs to Milestone 5. To repeat the check, set `LLAMA_CLOUD_API_KEY` locally and run `--parser llamaparse --parse-only` or omit `--parse-only` for extraction. Review LlamaCloud's retention terms before uploading any non-public document.

Current parser API references: [Docling conversion](https://docling-project.github.io/docling/getting_started/quickstart/), [Docling per-page text export](https://docling-project.github.io/docling/reference/docling_document/), [LlamaCloud parse quick start](https://developers.llamaindex.ai/llamaparse/parse/getting_started/).
