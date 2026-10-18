"""Show compact evidence for date false positives in the development baseline."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    references = json.loads((ROOT / "references/development.json").read_text(encoding="utf-8"))
    by_title = {item["title"]: item for item in references["contracts"]}
    for path in (ROOT / "outputs/text_runs").glob("*.json"):
        run = json.loads(path.read_text(encoding="utf-8"))
        title = run["document_id"]
        if title not in by_title or run["metadata"]["prompt_version"] != "text-v2":
            continue
        for label, key in (("Agreement Date", "agreement_date"), ("Effective Date", "effective_date")):
            reference = by_title[title]["fields"][label]
            prediction = (run.get("extraction") or {}).get(key)
            if reference["status"] == "missing" and prediction and prediction["status"] == "found":
                print(f"{title}\n  {label}: {prediction['value']}")
                for evidence in prediction["evidence"]:
                    print(f"  quote: {evidence['quote'][:240]!r}")


if __name__ == "__main__":
    main()
