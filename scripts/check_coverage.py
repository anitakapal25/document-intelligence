import json
from pathlib import Path
import csv

CATEGORIES = (
    "Document Name",
    "Parties",
    "Agreement Date",
    "Effective Date",
    "Governing Law",
)


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    path = root / "data/raw/cuad_benchmark/train_separate_questions.json"

    with path.open(encoding="utf-8") as file:
        contracts = json.load(file)["data"]

    counts = {category: 0 for category in CATEGORIES}
    rows = []

    for contract in contracts:
        present = {category: False for category in CATEGORIES}

        for paragraph in contract["paragraphs"]:
            for qa in paragraph["qas"]:
                category = qa["id"].rsplit("__", 1)[-1].rsplit("_", 1)[0]

                if category in present and qa["answers"]:
                    present[category] = True

        for category, has_answer in present.items():
            if has_answer:
                counts[category] += 1

        rows.append({"title": contract["title"], **present})

    output_path = root / "data/processed/train_coverage.csv"
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["title", *CATEGORIES])
        writer.writeheader()
        writer.writerows(rows)

    print("Coverage table:", output_path)
    print("Training contracts:", len(contracts))
    for category, count in counts.items():
        print(f"{category}: {count} present, {len(contracts) - count} absent")


if __name__ == "__main__":
    main()