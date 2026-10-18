"""Read-only final audit of cached schemas, provenance, and every quotation."""
import hashlib
import json

from app.schemas import ExtractionRun
from scripts.freeze_pilot import verify_frozen
from scripts.run_held_out import ROOT, OUT


def main():
    verify_frozen()
    manifest = json.loads((ROOT / "manifests/held_out.json").read_text())
    protocol = json.loads((OUT / "protocol.json").read_text())
    if hashlib.sha256((ROOT / "references/held_out.json").read_bytes()).hexdigest() != protocol["references_sha256"]:
        raise ValueError("Reference labels changed")
    test = json.loads((ROOT / "data/raw/cuad_benchmark/test.json").read_text(encoding="utf-8"))
    by_title = {c["title"]: c for c in test["data"]}
    quotes = runs = 0
    for mode in ("text", "pdf"):
        for i, item in enumerate(manifest["contracts"]):
            saved = json.loads((OUT / "runs" / f"{i:02}_{mode}.json").read_text())
            if saved["protocol"] != protocol:
                raise ValueError("Mismatched protocol")
            run = ExtractionRun.model_validate(saved["run"])
            if run.document_id != item["title"]:
                raise ValueError("Wrong document identity")
            runs += 1
            if mode == "text":
                source = "\n\n".join(p["context"] for p in by_title[item["title"]]["paragraphs"])
                if hashlib.sha256(source.encode()).hexdigest() != saved["source_sha256"]:
                    raise ValueError("Text fingerprint mismatch")
                sources = {None: source}
            else:
                parsed_path = OUT / "parsed" / f"{i:02}.json"
                parsed = json.loads(parsed_path.read_text()) if parsed_path.exists() else None
                if parsed and parsed["pdf_sha256"] != saved["source_sha256"]:
                    raise ValueError("PDF fingerprint mismatch")
                sources = {p["number"]: p["text"] for p in parsed["document"]["pages"]} if parsed else {}
            if run.extraction:
                for name in type(run.extraction).model_fields:
                    for evidence in getattr(run.extraction, name).evidence:
                        source = sources[evidence.page]
                        if source[evidence.start:evidence.end] != evidence.quote:
                            raise ValueError(f"Quotation mismatch: {mode}/{i}/{name}")
                        if source.count(evidence.quote) != evidence.occurrences:
                            raise ValueError("Occurrence count mismatch")
                        quotes += 1
    summary = {"runs_schema_validated": runs, "quotations_source_validated": quotes,
               "reference_hash_verified": True, "frozen_sources_verified": True}
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports/held_out_audit.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
