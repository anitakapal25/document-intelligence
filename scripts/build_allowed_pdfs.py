"""Record exact public CUAD and synthetic PDF bytes accepted by the pilot API."""

import hashlib
import json
from pathlib import Path

from scripts.compare_parsers import ROOT, pdf_for


def main() -> None:
    development = json.loads((ROOT / "manifests/development.json").read_text(encoding="utf-8"))
    sources = [(item["title"], pdf_for(item["title"])) for item in development["contracts"]]
    synthetic = ROOT / "data/synthetic/sample_agreement.pdf"
    if synthetic.is_file():
        sources.append(("synthetic-sample-agreement", synthetic))
    entries = []
    for title, path in sources:
        contents = path.read_bytes()
        entries.append({"document_id": title, "sha256": hashlib.sha256(contents).hexdigest(),
                        "bytes": len(contents)})
    target = ROOT / "configs/allowed_pdfs.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"purpose": "exact-byte CUAD/synthetic pilot allowlist",
                                  "contracts": entries}, indent=2) + "\n", encoding="utf-8")
    print(f"Allowed PDFs: {len(entries)}; saved {target}")


if __name__ == "__main__":
    main()
