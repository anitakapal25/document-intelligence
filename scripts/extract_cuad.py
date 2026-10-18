"""Run one manifest-selected development contract through text extraction."""

import argparse
import hashlib
import json
from pathlib import Path

from app.extractor import MODEL, PROMPT_VERSION, extract_text


ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=int, required=True, help="Development manifest index (0-19)")
    parser.add_argument("--dry-run", action="store_true", help="Check input without an API call")
    args = parser.parse_args()

    manifest = json.loads((ROOT / "manifests/development.json").read_text(encoding="utf-8"))
    if not 0 <= args.index < len(manifest["contracts"]):
        parser.error("index must be between 0 and 19")
    title = manifest["contracts"][args.index]["title"]
    source_data = json.loads(
        (ROOT / "data/raw/cuad_benchmark/train_separate_questions.json").read_text(encoding="utf-8")
    )
    contract = next(c for c in source_data["data"] if c["title"] == title)
    source = "\n\n".join(p["context"] for p in contract["paragraphs"])

    print(f"Contract: {title}")
    print(f"Source characters: {len(source)}")
    if args.dry_run:
        print("Dry run: no API request was made")
        return

    cache_key = hashlib.sha256(f"{MODEL}|{PROMPT_VERSION}|{source}".encode("utf-8")).hexdigest()
    output = ROOT / "outputs/text_runs" / f"{cache_key}.json"
    if output.exists():
        cached = json.loads(output.read_text(encoding="utf-8"))
        if cached.get("status") == "completed":
            print(f"Cached completed run: {output}")
            return

    run = extract_text(title, source)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(run.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"Status: {run.status.value}")
    print(f"Saved: {output}")


if __name__ == "__main__":
    main()
