"""Select a reproducible CUAD pilot sample without reading test answers."""

import hashlib
import json
import random
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "data" / "raw" / "cuad_benchmark"
OUTPUT = ROOT / "manifests"
FIELDS = ("Document Name", "Parties", "Agreement Date", "Effective Date", "Governing Law")
SEED = 42


def load_contracts(filename: str) -> list[dict]:
    with (DATASET / filename).open(encoding="utf-8") as file:
        return json.load(file)["data"]


def category_name(question_id: str) -> str:
    return question_id.rsplit("__", 1)[-1].rsplit("_", 1)[0]


def coverage(contract: dict) -> dict[str, bool]:
    present = {field: False for field in FIELDS}
    for paragraph in contract["paragraphs"]:
        for question in paragraph["qas"]:
            field = category_name(question["id"])
            if field in present and question["answers"]:
                present[field] = True
    return present


def text_fingerprint(contract: dict) -> str:
    # Normalize spacing to catch copies with different line wrapping.
    text = " ".join(p["context"] for p in contract["paragraphs"])
    normalized = re.sub(r"\s+", " ", text).strip().casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def select_development(contracts: list[dict]) -> list[dict]:
    rng = random.Random(SEED)
    by_title = {contract["title"]: contract for contract in contracts}
    selected = [
        by_title["LIMEENERGYCO_09_09_1999-EX-10-DISTRIBUTOR AGREEMENT"],
        by_title["WHITESMOKE,INC_11_08_2011-EX-10.26-PROMOTION AND DISTRIBUTION AGREEMENT"],
    ]
    selected.append(next(c for c in contracts if not coverage(c)["Parties"]))

    targets = {"Agreement Date": 3, "Effective Date": 4, "Governing Law": 3}
    for field, target in targets.items():
        while sum(not coverage(c)[field] for c in selected) < target:
            chosen = {c["title"] for c in selected}
            candidates = [
                c for c in contracts if c["title"] not in chosen and not coverage(c)[field]
            ]
            if not candidates:
                raise ValueError(f"Cannot meet coverage target for {field}")
            selected.append(rng.choice(candidates))

    chosen = {c["title"] for c in selected}
    remaining = [c for c in contracts if c["title"] not in chosen]
    rng.shuffle(remaining)
    selected.extend(remaining[: 20 - len(selected)])
    if len(selected) != 20 or len({c["title"] for c in selected}) != 20:
        raise ValueError("Development sample must contain 20 unique contracts")
    return selected


def select_test(contracts: list[dict], development_hashes: set[str]) -> list[dict]:
    # Do not inspect test questions or answers while selecting the held-out sample.
    candidates = [c for c in contracts if text_fingerprint(c) not in development_hashes]
    selected = random.Random(SEED).sample(candidates, 10)
    if len({c["title"] for c in selected}) != 10:
        raise ValueError("Test sample must contain 10 unique contracts")
    return selected


def write_manifest(filename: str, split: str, contracts: list[dict]) -> None:
    entries = []
    for contract in contracts:
        entry = {
            "title": contract["title"],
            "text_sha256": text_fingerprint(contract),
        }
        if split == "train":
            entry["annotated_fields"] = coverage(contract)
        entries.append(entry)

    manifest = {
        "dataset": "CUAD v1",
        "source_split": split,
        "seed": SEED,
        "contracts": entries,
    }
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT / filename).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    training = load_contracts("train_separate_questions.json")
    test = load_contracts("test.json")
    development = select_development(training)
    dev_hashes = {text_fingerprint(c) for c in development}
    held_out = select_test(test, dev_hashes)

    dev_titles = {c["title"] for c in development}
    test_titles = {c["title"] for c in held_out}
    test_hashes = {text_fingerprint(c) for c in held_out}
    if dev_titles & test_titles or dev_hashes & test_hashes:
        raise ValueError("Contract leakage between development and held-out samples")
    if len(dev_hashes) != 20 or len(test_hashes) != 10:
        raise ValueError("Duplicate contract text within a sample")

    write_manifest("development.json", "train", development)
    write_manifest("held_out.json", "test", held_out)
    print(f"Development: {len(development)} contracts; held-out: {len(held_out)} contracts")
    print("Title overlap: 0; normalized-text hash overlap: 0")
    for field in FIELDS:
        count = sum(coverage(c)[field] for c in development)
        print(f"Development {field}: {count} annotated, {20 - count} absent")
    print("Test answers were not used for selection or coverage reporting.")


if __name__ == "__main__":
    main()
