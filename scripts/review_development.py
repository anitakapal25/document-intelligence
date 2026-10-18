"""Print compact CUAD evidence for manual reference-label review."""

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FIELDS = ("Document Name", "Parties", "Agreement Date", "Effective Date", "Governing Law")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=int, help="Show one manifest entry")
    parser.add_argument("--full", action="store_true", help="Show complete answer spans")
    parser.add_argument("--split", choices=("development", "held_out"), default="development")
    args = parser.parse_args()
    manifest = json.loads((ROOT / f"manifests/{args.split}.json").read_text(encoding="utf-8"))
    filename = "test.json" if args.split == "held_out" else "train_separate_questions.json"
    dataset = json.loads(
        (ROOT / "data/raw/cuad_benchmark" / filename).read_text(encoding="utf-8")
    )
    by_title = {contract["title"]: contract for contract in dataset["data"]}
    for index, entry in enumerate(manifest["contracts"]):
        if args.index is not None and index != args.index:
            continue
        contract = by_title[entry["title"]]
        answers = {field: [] for field in FIELDS}
        for paragraph in contract["paragraphs"]:
            context = paragraph["context"]
            for question in paragraph["qas"]:
                field = question["id"].rsplit("__", 1)[-1]
                if field.rsplit("_", 1)[-1].isdigit():
                    field = field.rsplit("_", 1)[0]
                if field not in answers:
                    continue
                for answer in question["answers"]:
                    start, quote = answer["answer_start"], answer["text"]
                    if context[start : start + len(quote)] != quote:
                        raise ValueError(f"Invalid CUAD offset: {entry['title']} {field}")
                    answers[field].append(quote)

        print(f"\n[{index:02}] {entry['title']}")
        for field, quotes in answers.items():
            if not quotes:
                print(f"  {field}: ABSENT")
            else:
                previews = [" ".join(quote.split())[: None if args.full else 140] for quote in quotes]
                print(f"  {field} ({len(quotes)} spans): {' | '.join(previews)}")


if __name__ == "__main__":
    main()
