"""Check CUAD pilot manifests against their official source splits."""

import json

from build_manifests import OUTPUT, coverage, load_contracts, text_fingerprint


def validate(filename: str, split: str, source_file: str, expected: int) -> list[dict]:
    manifest = json.loads((OUTPUT / filename).read_text(encoding="utf-8"))
    assert manifest["source_split"] == split
    entries = manifest["contracts"]
    assert len(entries) == expected
    assert len({entry["title"] for entry in entries}) == expected
    assert len({entry["text_sha256"] for entry in entries}) == expected

    source = {contract["title"]: contract for contract in load_contracts(source_file)}
    for entry in entries:
        contract = source[entry["title"]]
        assert entry["text_sha256"] == text_fingerprint(contract)
        if split == "train":
            assert entry["annotated_fields"] == coverage(contract)
        else:
            assert "annotated_fields" not in entry
    return entries


def main() -> None:
    development = validate("development.json", "train", "train_separate_questions.json", 20)
    held_out = validate("held_out.json", "test", "test.json", 10)
    assert not ({e["title"] for e in development} & {e["title"] for e in held_out})
    assert not ({e["text_sha256"] for e in development} & {e["text_sha256"] for e in held_out})
    print("Manifest validation passed: 20 development, 10 held-out, no selected leakage")


if __name__ == "__main__":
    main()
