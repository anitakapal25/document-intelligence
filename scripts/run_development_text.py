"""Run the 20 selected text contracts with caching and a pilot cost guard."""

import hashlib
import json
from pathlib import Path

from app.analytics import estimated_openai_cost
from app.extractor import MODEL, PROMPT_VERSION, extract_text


ROOT = Path(__file__).resolve().parent.parent
MAX_BATCH_ESTIMATED_USD = 1.00


def main() -> None:
    manifest = json.loads((ROOT / "manifests/development.json").read_text(encoding="utf-8"))
    training = json.loads((ROOT / "data/raw/cuad_benchmark/train_separate_questions.json").read_text(encoding="utf-8"))
    by_title = {contract["title"]: contract for contract in training["data"]}
    sources = []
    for item in manifest["contracts"]:
        title = item["title"]
        source = "\n\n".join(p["context"] for p in by_title[title]["paragraphs"])
        key = hashlib.sha256(f"{MODEL}|{PROMPT_VERSION}|{source}".encode()).hexdigest()
        output = ROOT / "outputs/text_runs" / f"{key}.json"
        sources.append((title, source, output))
    pending = [(title, source, output) for title, source, output in sources if not output.exists() or
               json.loads(output.read_text(encoding="utf-8")).get("status") != "completed"]
    # Conservative preflight: 1 token per 3 source chars + 4096 output tokens per request.
    upper_estimate = sum((len(source) / 3 * 0.10 + 4096 * 0.50) / 1_000_000
                         for _, source, _ in pending)
    print(f"Selected: {len(sources)}; pending: {len(pending)}; rough maximum new OpenAI cost: ${upper_estimate:.3f}", flush=True)
    if upper_estimate > MAX_BATCH_ESTIMATED_USD:
        raise RuntimeError("Batch exceeds $1 estimated safety threshold")
    spent = 0.0
    for index, (title, source, output) in enumerate(pending, start=1):
        run = extract_text(title, source)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(run.model_dump_json(indent=2) + "\n", encoding="utf-8")
        spent += estimated_openai_cost(run.metadata.model_dump()) or 0.0
        print(f"{index}/{len(pending)} {run.status.value}: {title[:62]} (estimated ${spent:.4f})", flush=True)
        if spent >= MAX_BATCH_ESTIMATED_USD:
            raise RuntimeError("Stopped at $1 estimated batch threshold")


if __name__ == "__main__":
    main()
