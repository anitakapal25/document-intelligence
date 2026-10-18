"""Matched development-PDF comparison with parse/run caches and a cost guard."""

import argparse
import hashlib
import json
import time
from pathlib import Path

import duckdb

from app.analytics import estimated_openai_cost
from app.evaluation import aggregate, score_run
from app.extractor import MODEL, PROMPT_VERSION, SYSTEM_PROMPT
from app.parsers import ParsedDocument, parse_pdf
from app.pdf_workflow import MAX_CHUNKS, extract_parsed, page_chunks
from app.tracing import finish_tracing, metadata_span, start_tracing


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs/parser_comparison"
PARSERS = ("docling", "llamaparse")
SELECTED_INDICES = (0, 2, 4)  # Present fields and deliberately absent annotations.
LIMIT_USD = 20.0


def identity() -> dict:
    from app.schemas import ModelExtraction
    import app.evaluation as evaluation
    import app.pdf_workflow as workflow

    def digest(value: bytes) -> str:
        return hashlib.sha256(value).hexdigest()

    return {
        "model": MODEL, "prompt_version": PROMPT_VERSION,
        "prompt_sha256": digest(SYSTEM_PROMPT.encode()),
        "schema_sha256": digest(json.dumps(ModelExtraction.model_json_schema(), sort_keys=True).encode()),
        "workflow_sha256": digest(Path(workflow.__file__).read_bytes()),
        "scorer_sha256": digest(Path(evaluation.__file__).read_bytes()),
        "chunk_size": 3000, "chunk_overlap": 200, "max_chunks": MAX_CHUNKS,
        "docling_version": "2.140.0", "llamacloud_version": "2.18.0",
        "llamaparse_tier": "cost_effective", "llamaparse_version": "2026-09-28",
    }


def selected() -> list[dict]:
    manifest = json.loads((ROOT / "manifests/development.json").read_text(encoding="utf-8"))
    return [manifest["contracts"][index] for index in SELECTED_INDICES]


def pdf_for(title: str) -> Path:
    matches = [path for path in (ROOT / "data/raw/cuad_pdfs/development").iterdir()
               if path.stem.casefold() == title.casefold() and path.suffix.casefold() == ".pdf"]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one PDF for selected title: {title}")
    return matches[0]


def prior_cost() -> float:
    db = ROOT / "data/processed/benchmark.duckdb"
    recorded = 0.0
    if db.exists():
        connection = duckdb.connect(str(db), read_only=True)
        try:
            recorded = float(connection.execute("SELECT coalesce(sum(estimated_openai_usd), 0) FROM runs").fetchone()[0])
        finally:
            connection.close()
    cached = 0.0
    for path in (OUT / "runs").glob("*.json"):
        saved = json.loads(path.read_text(encoding="utf-8"))
        cached += estimated_openai_cost(saved["run"]["metadata"]) or 0.0
    return recorded + cached


def load_or_parse(path: Path, parser: str, tracer) -> tuple[ParsedDocument, float]:
    target = OUT / "parsed" / f"{path.stem}_{parser}.json"
    if target.exists():
        saved = json.loads(target.read_text(encoding="utf-8"))
        if saved["pdf_sha256"] != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError(f"PDF changed since parse cache: {path.name}")
        return ParsedDocument.model_validate(saved["document"]), saved["parse_seconds"]
    started = time.perf_counter()
    with metadata_span(tracer, "parse_pdf", parser=parser, pdf_sha256=hashlib.sha256(path.read_bytes()).hexdigest()):
        document = parse_pdf(path, parser=parser)
    seconds = time.perf_counter() - started
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"pdf_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                  "parse_seconds": seconds, "document": document.model_dump()}, indent=2),
                      encoding="utf-8")
    return document, seconds


def main() -> None:
    arguments = argparse.ArgumentParser()
    arguments.add_argument("--parse-only", action="store_true")
    args = arguments.parse_args()
    configuration = identity()
    OUT.mkdir(parents=True, exist_ok=True)
    config_file = OUT / "configuration.json"
    if config_file.exists() and json.loads(config_file.read_text(encoding="utf-8")) != configuration:
        raise ValueError("Comparison configuration changed; use a new output directory for a new experiment")
    config_file.write_text(json.dumps(configuration, indent=2) + "\n", encoding="utf-8")
    refs = json.loads((ROOT / "references/development.json").read_text(encoding="utf-8"))
    references = {item["title"]: item for item in refs["contracts"]}
    train = json.loads((ROOT / "data/raw/cuad_benchmark/train_separate_questions.json").read_text(encoding="utf-8"))
    contexts = {item["title"]: [p["context"] for p in item["paragraphs"]] for item in train["data"]}
    tracer = start_tracing()
    rows = []
    spent = prior_cost()
    try:
        for item in selected():
            title = item["title"]
            path = pdf_for(title)
            for parser in PARSERS:
                parsed, parse_seconds = load_or_parse(path, parser, tracer)
                chunks = page_chunks(parsed)
                print(f"{title[:40]} | {parser}: {len(parsed.pages)} pages, {len(chunks)} chunks, parse {parse_seconds:.1f}s", flush=True)
                if args.parse_only:
                    continue
                target = OUT / "runs" / f"{title}_{parser}.json"
                if target.exists():
                    saved = json.loads(target.read_text(encoding="utf-8"))
                    if saved["configuration"] != configuration:
                        raise ValueError(f"Stale run cache: {target.name}")
                    if saved["run"]["status"] == "failed" and saved["run"].get("error_code") == "APIConnectionError":
                        saved = None  # A sandbox network failure is not a completed benchmark run.
                else:
                    saved = None
                if saved is None:
                    # Conservative preflight: assume at most 20K input + 4K output tokens per chunk.
                    reserve = len(chunks) * (20_000 * 0.10 + 4_000 * 0.50) / 1_000_000
                    if spent + reserve > LIMIT_USD:
                        raise RuntimeError(f"Estimated API budget guard: ${spent:.2f} spent, ${reserve:.2f} reserved")
                    started = time.perf_counter()
                    with metadata_span(tracer, "extract_pdf", parser=parser, pages=len(parsed.pages),
                                       chunks=len(chunks), pdf_sha256=hashlib.sha256(path.read_bytes()).hexdigest()) as span:
                        run = extract_parsed(title, parsed)
                        if span is not None:
                            span.set_attribute("status", run.status.value)
                            span.set_attribute("input_tokens", run.metadata.input_tokens or 0)
                            span.set_attribute("output_tokens", run.metadata.output_tokens or 0)
                    elapsed = time.perf_counter() - started
                    saved = {"configuration": configuration, "parse_seconds": parse_seconds,
                             "extract_seconds": elapsed, "run": run.model_dump(mode="json")}
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(json.dumps(saved, indent=2) + "\n", encoding="utf-8")
                    spent += estimated_openai_cost(saved["run"]["metadata"]) or reserve
                run = saved["run"]
                scores = score_run(run, references[title], contexts[title])
                rows.append({"title": title, "parser": parser, "pages": len(parsed.pages),
                             "chunks": len(chunks), "parse_seconds": saved["parse_seconds"],
                             "extract_seconds": saved["extract_seconds"], "status": run["status"],
                             "input_tokens": run["metadata"]["input_tokens"],
                             "output_tokens": run["metadata"]["output_tokens"],
                             "openai_usd_estimate": estimated_openai_cost(run["metadata"]),
                             "scores": scores})
                print(f"  extraction {run['status']}, {saved['extract_seconds']:.1f}s", flush=True)
    finally:
        finish_tracing(tracer)
    if args.parse_only:
        return
    report = {"configuration": configuration, "contracts": len(selected()), "rows": rows,
              "aggregate": {parser: aggregate([row["scores"] for row in rows if row["parser"] == parser])
                            for parser in PARSERS}}
    (OUT / "comparison.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(OUT / "comparison.json")


if __name__ == "__main__":
    main()
