"""Parse and extract one local PDF; results remain under ignored outputs/."""

import argparse
from pathlib import Path

from app.pdf_workflow import extract_parsed, page_chunks
from app.parsers import parse_pdf


ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--parser", choices=("docling", "llamaparse"), default="docling")
    parser.add_argument("--parse-only", action="store_true", help="Do not call OpenAI")
    args = parser.parse_args()
    parsed = parse_pdf(args.pdf, parser=args.parser)
    chunks = page_chunks(parsed)
    print(f"Parser: {parsed.parser}; pages: {len(parsed.pages)}; chunks: {len(chunks)}")
    for page in parsed.pages:
        print(f"Page {page.number}: {len(page.text)} characters")
    if args.parse_only:
        return
    run = extract_parsed(args.pdf.stem, parsed)
    output = ROOT / "outputs/pdf_runs" / f"{args.pdf.stem}_{args.parser}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(run.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"Status: {run.status.value}; saved: {output}")


if __name__ == "__main__":
    main()
