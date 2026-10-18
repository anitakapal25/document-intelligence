"""One frozen test attempt per contract/path; resumable without rerunning failures."""
import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from app.analytics import estimated_openai_cost
from app.extractor import MODEL, PROMPT_VERSION, extract_text
from app.parsers import ParsedDocument, parse_pdf
from app.pdf_workflow import extract_parsed, page_chunks
from app.schemas import ExtractionRun, RunMetadata, RunStatus
from scripts.compare_parsers import prior_cost
from scripts.freeze_pilot import verify_frozen as verify_freeze

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs/held_out"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--mode", choices=("text", "pdf"), required=True)
    args = cli.parse_args()
    verify_freeze()
    manifest = json.loads((ROOT / "manifests/held_out.json").read_text())
    test = json.loads((ROOT / "data/raw/cuad_benchmark/test.json").read_text(encoding="utf-8"))
    by_title = {c["title"]: c for c in test["data"]}
    protocol = {"freeze_sha256": sha(ROOT / "configs/frozen_pilot.json"),
                "references_sha256": sha(ROOT / "references/held_out.json"),
                "paths": ["cuad_supplied_text", "pdf:docling"],
                "policy": "First attempt retained including failures. No tuning or selective reruns. SDK bounded retries remain frozen.",
                "budget_usd": 20}
    protocol_path = OUT / "protocol.json"
    if protocol_path.exists() and json.loads(protocol_path.read_text()) != protocol:
        raise ValueError("Test protocol changed")
    write(protocol_path, protocol)
    spent = prior_cost()
    for existing in (OUT / "runs").glob("*.json"):
        saved = json.loads(existing.read_text())
        spent += saved["budget_charge_usd"]
    for i, item in enumerate(manifest["contracts"]):
        target = OUT / "runs" / f"{i:02}_{args.mode}.json"
        if target.exists():
            print(f"Cached {target.name}; first attempt preserved", flush=True)
            continue
        marker = OUT / "started" / f"{i:02}_{args.mode}.json"
        if marker.exists():
            raise RuntimeError(f"Interrupted attempt {marker.name}; inspect before any retry")
        title = item["title"]
        started = time.perf_counter()
        parse_seconds = 0.0
        reserve = 0.0
        pages = chunks = None
        source_hash = None
        run = None
        print(f"START {i + 1}/10 {args.mode}: {title}", flush=True)
        try:
            if args.mode == "text":
                source = "\n\n".join(p["context"] for p in by_title[title]["paragraphs"])
                source_hash = hashlib.sha256(source.encode()).hexdigest()
                # UTF-8 byte count is a conservative input-token estimate; include prompt/schema and retries.
                reserve = 3 * ((len(source.encode()) + 20000) * .10 + 4096 * .50) / 1_000_000
            else:
                paths = [p for p in (ROOT / "data/raw/cuad_pdfs/held_out").glob("*")
                         if p.stem.casefold() == title.casefold()]
                if len(paths) != 1:
                    raise ValueError("PDF match is not unique")
                source_hash = sha(paths[0])
                parse_start = time.perf_counter()
                parsed = parse_pdf(paths[0], parser="docling")
                parse_seconds = time.perf_counter() - parse_start
                write(OUT / "parsed" / f"{i:02}.json", {"pdf_sha256": source_hash,
                      "parse_seconds": parse_seconds, "document": parsed.model_dump()})
                pages = len(parsed.pages)
                chunks = len(page_chunks(parsed))
                reserve = chunks * .0123  # 3 attempts, 20K input + 4096 output per chunk.
                print(f"Parsed {pages} pages / {chunks} chunks in {parse_seconds:.1f}s", flush=True)
            if spent + reserve > 20:
                raise RuntimeError("Estimated $20 project API guard reached")
            write(marker, {"started_utc": datetime.now(timezone.utc).isoformat(),
                           "reserved_usd": reserve, "source_sha256": source_hash})
            extract_start = time.perf_counter()
            run = extract_text(title, source) if args.mode == "text" else extract_parsed(title, parsed)
            extract_seconds = time.perf_counter() - extract_start
        except (ValueError, RuntimeError) as exc:
            # Preserve deterministic limit/parser errors instead of dropping difficult contracts.
            if "budget" in str(exc).lower() or "$20" in str(exc):
                raise
            run = ExtractionRun(document_id=title, status=RunStatus.FAILED, extraction=None,
                metadata=RunMetadata(model=MODEL, source="cuad_supplied_text" if args.mode == "text" else "pdf:docling",
                                     prompt_version=PROMPT_VERSION, elapsed_ms=0, input_tokens=None,
                                     output_tokens=None, response_id=None), error_code=f"{type(exc).__name__}: {exc}")
            extract_seconds = 0.0
        estimate = estimated_openai_cost(run.metadata.model_dump())
        charge = estimate if run.status == RunStatus.COMPLETED and estimate is not None else reserve
        saved = {"run": run.model_dump(mode="json"), "source_sha256": source_hash,
                 "protocol": protocol, "pages": pages, "chunks": chunks,
                 "parse_seconds": parse_seconds, "extract_seconds": extract_seconds,
                 "total_seconds": time.perf_counter() - started,
                 "budget_charge_usd": charge, "estimated_openai_usd": estimate,
                 "completed_utc": datetime.now(timezone.utc).isoformat()}
        write(target, saved)
        spent += charge
        print(f"SAVED {target.name}: {run.status.value}; elapsed {saved['total_seconds']:.1f}s; budget accounted ${spent:.3f}", flush=True)


if __name__ == "__main__":
    main()
