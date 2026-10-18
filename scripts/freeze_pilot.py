"""Record the tested extraction configuration before held-out evaluation."""

import hashlib
import json
import argparse
from pathlib import Path

from scripts.compare_parsers import OUT, PARSERS, ROOT, identity, selected


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_frozen() -> dict:
    """Read-only verification works from tracked artifacts without old run caches."""
    target = ROOT / "configs/frozen_pilot.json"
    frozen = json.loads(target.read_text(encoding="utf-8"))
    if frozen["configuration"] != identity():
        raise ValueError("Current configuration differs from freeze")
    for name, expected in frozen["source_sha256"].items():
        if sha(ROOT / name) != expected:
            raise ValueError(f"Frozen source changed: {name}")
    return frozen


def main() -> None:
    comparison = json.loads((OUT / "comparison.json").read_text(encoding="utf-8"))
    configuration = identity()
    if comparison["configuration"] != configuration:
        raise ValueError("Working configuration differs from completed development comparison")
    expected = {(item["title"], parser) for item in selected() for parser in PARSERS}
    actual = {(row["title"], row["parser"]) for row in comparison["rows"]}
    if expected != actual or any(row["status"] != "completed" for row in comparison["rows"]):
        raise ValueError("Matched development comparison is incomplete")
    frozen = {
        "purpose": "pilot held-out evaluation; change requires a new development experiment",
        "primary_parser": "docling",
        "comparison_parser": "llamaparse",
        "configuration": configuration,
        "source_sha256": {
            name: sha(ROOT / name) for name in (
                "app/extractor.py", "app/parsers.py", "app/pdf_workflow.py",
                "app/schemas.py", "app/evidence.py", "app/evaluation.py",
                "manifests/development.json", "manifests/held_out.json",
            )
        },
    }
    target = ROOT / "configs/frozen_pilot.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and json.loads(target.read_text(encoding="utf-8")) != frozen:
        raise ValueError("Existing freeze differs from current code or manifests")
    target.write_text(json.dumps(frozen, indent=2) + "\n", encoding="utf-8")
    print(target)


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--verify-only", action="store_true")
    if cli.parse_args().verify_only:
        verify_frozen()
        print("Frozen configuration and source hashes verified")
    else:
        main()
