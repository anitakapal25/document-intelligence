"""Fetch selected official CUAD PDFs from the Atticus Project's Hugging Face mirror."""

import argparse
import json
from pathlib import Path
from urllib.parse import quote

import requests


ROOT = Path(__file__).resolve().parent.parent
API = "https://huggingface.co/api/datasets/theatticusproject/cuad/tree/main/CUAD_v1/full_contract_pdf"
BASE = "https://huggingface.co/datasets/theatticusproject/cuad/resolve/main/"


def selected_titles(split: str) -> list[str]:
    manifest = json.loads((ROOT / f"manifests/{split}.json").read_text(encoding="utf-8"))
    return [entry["title"] for entry in manifest["contracts"]]


def match_paths(paths: list[str], titles: list[str]) -> tuple[dict[str, str], list[str]]:
    by_stem = {Path(path).stem.casefold(): path for path in paths if path.lower().endswith(".pdf")}
    found = {title: by_stem[title.casefold()] for title in titles if title.casefold() in by_stem}
    missing = [title for title in titles if title not in found]
    return found, missing


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("development", "held_out"), default="development")
    parser.add_argument("--download", action="store_true", help="Download matched PDFs")
    args = parser.parse_args()
    response = requests.get(API, params={"recursive": "true", "limit": 1000}, timeout=60)
    response.raise_for_status()
    paths = [item["path"] for item in response.json()]
    found, missing = match_paths(paths, selected_titles(args.split))
    print(f"{args.split}: {len(found)} exact filename matches, {len(missing)} unmatched")
    for title in missing:
        print(f"Unmatched: {title}")
    if not args.download:
        return
    target_dir = ROOT / "data/raw/cuad_pdfs" / args.split
    target_dir.mkdir(parents=True, exist_ok=True)
    for title, path in found.items():
        target = target_dir / Path(path).name
        if target.is_file() and target.read_bytes().startswith(b"%PDF-"):
            print(f"Cached: {target.name}")
            continue
        url = BASE + quote(path, safe="/")
        with requests.get(url, stream=True, timeout=120) as download:
            download.raise_for_status()
            with target.open("wb") as output:
                for chunk in download.iter_content(chunk_size=1024 * 1024):
                    output.write(chunk)
        if not target.read_bytes().startswith(b"%PDF-"):
            raise ValueError(f"Downloaded file is not a PDF: {target}")
        print(f"Downloaded: {target.name}")


if __name__ == "__main__":
    main()
