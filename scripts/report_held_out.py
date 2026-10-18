"""Publish aggregate pilot results and store full local evaluations in DuckDB."""
import hashlib
import json
import platform
from importlib.metadata import version
from collections import Counter
from statistics import median

from app.analytics import connect, save_run
from app.evaluation import FIELD_NAMES, aggregate, score_run
from scripts.evaluate_runs import report_group
from scripts.run_held_out import ROOT, OUT, sha


def main():
    protocol = json.loads((OUT / "protocol.json").read_text())
    if sha(ROOT / "references/held_out.json") != protocol["references_sha256"]:
        raise ValueError("References changed after test started")
    refs = json.loads((ROOT / "references/held_out.json").read_text())
    test = json.loads((ROOT / "data/raw/cuad_benchmark/test.json").read_text(encoding="utf-8"))
    contexts = {c["title"]: [p["context"] for p in c["paragraphs"]] for c in test["data"]}
    db = connect(ROOT / "data/processed/benchmark.duckdb")
    lines = ["# Frozen held-out pilot report", "",
             "Ten contracts selected with seed 42 from CUAD's official 102-contract test split; 20 training contracts were used for development. Selected title and normalized-text overlap checks passed. This is a small portfolio pilot, not a production accuracy estimate.", "",
             "Model, prompt, schema, parsers, chunking, scorer, and manifests were frozen before test labels were opened. Reference values were agent-reviewed against answer spans and surrounding source text before predictions; this is not independent human adjudication. References and protocol hashes are recorded in `reports/held_out_metrics.json`. No tuning or selective reruns followed test results.", "",
             "Aliases and former names were consolidated to entities. Original CUAD title extent and OCR spellings were retained. Missing means no CUAD answer annotation, not proof of absence in the complete document. Blank/year-only dates and conditional dates without a definite calendar date were marked ambiguous. New Jersey and Delaware are outside the frozen jurisdiction lookup: two governing-law labels are explicitly unscorable, with their actual values retained in the reference file.", "",
             "Wrong replacements count FP + FN. Ambiguous/unscorable references are excluded from value scores. Processing failures are reported separately and excluded from value denominators, so read F1 together with failure counts and support. A completed run means processing succeeded, not that extracted facts are correct.", "",
             "Evidence token F1 uses the best reference/prediction quotation pair; it is not a measure of complete evidence coverage. Missing quotations are reported through reference support versus scored-pair counts. Span IoU applies only to supplied text; PDF page-relative offsets have no direct CUAD alignment.", ""]
    metrics = {"protocol": protocol, "groups": {}, "contracts": [],
               "runtime": {"python": platform.python_version(), "os": platform.system(),
                           "packages": {p: version(p) for p in ("openai", "pydantic", "docling", "llama-index-core", "duckdb")}}}
    lines += ["Reference positive support: 10 document names, 24 party entities across 10 contracts, 7 agreement dates, 4 effective dates, and 7 supported governing-law values. Two additional jurisdictions are excluded by the frozen normalizer. Agreement dates have 1 absent and 2 ambiguous labels; effective dates have 3 absent and 3 ambiguous labels; governing law has 1 absent label.", ""]
    errors = ["# Held-out error review (no subsequent tuning)", ""]
    for mode in ("text", "pdf"):
        items, records = [], []
        for i, reference in enumerate(refs["contracts"]):
            path = OUT / "runs" / f"{i:02}_{mode}.json"
            if not path.exists():
                raise ValueError(f"Missing first attempt: {path.name}")
            saved = json.loads(path.read_text())
            if saved["protocol"] != protocol:
                raise ValueError("Run protocol mismatch")
            run = saved["run"]
            if run["document_id"] != reference["title"]:
                raise ValueError("Run title mismatch")
            scores = score_run(run, reference, contexts[reference["title"]])
            save_run(db, hashlib.sha256(path.read_bytes()).hexdigest(), run, scores)
            items.append((run, scores))
            records.append(saved)
            metrics["contracts"].append({"index": i, "mode": mode, "title": run["document_id"],
                "status": run["status"], "error_code": run["error_code"], "pages": saved["pages"],
                "chunks": saved["chunks"], "total_seconds": saved["total_seconds"],
                "parse_seconds": saved["parse_seconds"], "extract_seconds": saved["extract_seconds"],
                "estimated_openai_usd": saved["estimated_openai_usd"], "scores": scores})
            if run["error_code"]:
                errors += [f"- {mode} / {i:02}: `{run['error_code']}`."]
            for field, score in scores.items():
                if score["fp"] or score["fn"] or score["prediction_status"] in ("failed", "processing_failed"):
                    predicted = (run.get("extraction") or {}).get(FIELD_NAMES[field]) or {}
                    errors += [f"- {mode} / {i:02} / {field}: prediction {score['prediction_status']}; TP {score['tp']}, FP {score['fp']}, FN {score['fn']}. Reference: `{reference['fields'][field]['value']}`; prediction: `{predicted.get('value')}`."]
        source = "cuad_supplied_text" if mode == "text" else "pdf:docling"
        lines += report_group(source, items)
        totals = sorted(r["total_seconds"] for r in records)
        lines += [f"Observed wall time: median {median(totals):.1f}s, nearest-rank p95 {totals[-1]:.1f}s; includes parse/extraction for PDFs. Total parse time {sum(r['parse_seconds'] for r in records):.1f}s. Times describe this local machine, not Cloud Run performance.", ""]
        metrics["groups"][source] = {"fields": aggregate([s for _, s in items]),
            "statuses": dict(Counter(r["run"]["status"] for r in records)),
            "wall_median_seconds": median(totals), "wall_p95_seconds": totals[-1],
            "estimated_openai_usd": sum(r["estimated_openai_usd"] or 0 for r in records),
            "known_cost_runs": sum(r["estimated_openai_usd"] is not None for r in records)}
    db.close()
    comparison = json.loads((ROOT / "outputs/parser_comparison/comparison.json").read_text())
    lines += ["## Controlled parser comparison (development only)", "",
              "Three identical development PDFs were processed by Docling and LlamaParse with the same model, prompt, schema and chunk settings. This comparison was completed before the freeze; LlamaParse was not rerun on the held-out sample.", "",
              "| Parser | Contracts | Parse seconds | Extraction seconds | Estimated OpenAI USD |", "| --- | ---: | ---: | ---: | ---: |"]
    for parser in ("docling", "llamaparse"):
        rows = [r for r in comparison["rows"] if r["parser"] == parser]
        lines.append(f"| {parser} | {len(rows)} | {sum(r['parse_seconds'] for r in rows):.1f} | {sum(r['extract_seconds'] for r in rows):.1f} | {sum(r['openai_usd_estimate'] or 0 for r in rows):.5f} |")
    metrics["development_parser_comparison"] = comparison
    lines += ["", "Development value counts: Docling matched 1/3 names and 1/2 scorable agreement dates; LlamaParse matched 2/3 and 2/2. Both matched 6/6 parties and 2/2 governing-law values. Effective dates had no scorable fixed-date positives. This sample cannot establish a general parser winner.", "",
              "## Error analysis and future work", "",
              "The supplied-text errors concentrate in the OCR-corrupted PrimeEnergy contract and the extent of the STW title/entity names. Exact matching penalizes OCR correction and added suffixes, so not every mismatch is a factual extraction error. The frozen references are left unchanged.", "",
              "On PDFs, short aliases such as Integra, Fleet, Vapotherm and COFS survive punctuation-only entity deduplication. Several contracts yield conflicting titles from different pages or exhibits, so the scalar merger returns ambiguous. The 88-page Pacira contract exceeds 80 chunks and fails before any model call. It remains in the ten-contract support and failure counts. The Photronics effective-date prediction is false-present against an absent CUAD annotation, which is an annotation disagreement rather than proof that the date is factually wrong.", "",
              "Future development experiments should evaluate document-level alias resolution, main-agreement versus exhibit scope, and explicit long-document routing. These changes were not made for this test. Broader jurisdiction support and independent reference adjudication should precede stronger quality claims.", "",
              "## Limits and deployment status", "",
              "Costs use the frozen estimate of $0.10/M input and $0.50/M output tokens. They exclude provider charges for failed attempts with unavailable usage, LlamaParse fees, cloud charges, discounts, and tax. Known token costs are not a billing statement. The runner conservatively reserves for unknown usage and bounded retries against the $20 project allowance.", "",
              "Long documents can exceed the 200,000-character supplied-text limit or 80-chunk PDF limit. Cross-page title/date conflicts can produce ambiguous values; entity alias matching is deliberately strict. OCR spelling errors can penalize otherwise corrected PDF values. These are observed or designed pilot limitations, not reasons to remove contracts from the report. The frozen model identifier is a provider model name rather than an immutable weight snapshot; later reruns may differ even with the same files.", "",
              "Local PDF wall time reached 1,216 seconds (over 20 minutes), exceeding the proposed 900-second synchronous service timeout. These uncontrolled local timings include first-use model loading/download effects and are not hosted latency measurements. OCR model weights were not content-hashed at the original freeze, which limits exact parser reproducibility.", "",
              "FastAPI and the upload UI are verified locally. Docker build, shared Firestore ledger, private Cloud Run deployment, and cloud upload latency remain unverified pending infrastructure/billing. The deployed upload flow is not claimed complete. The current synchronous configuration is unsuitable for the observed broader PDF workload: add durable asynchronous jobs before claiming that workload supported in the cloud, or independently validate a narrower bounded input scope on the hosted service.", ""]
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    (reports / "held_out.md").write_text("\n".join(lines), encoding="utf-8")
    (reports / "held_out_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    (reports / "held_out_errors.md").write_text("\n".join(errors) + "\n", encoding="utf-8")
    print(reports / "held_out.md")


if __name__ == "__main__":
    main()
