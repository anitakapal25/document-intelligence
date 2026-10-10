import json
from pathlib import Path


def save_contract(contract: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(contract, file, indent=2, ensure_ascii=False)


def main() -> None:
    contract = {
        "document_id": "sample-001",
        "document_name": "Sample Services Agreement",
        "parties": ["Acme Ltd", "Example Technologies","Third Company Ltd"],
        "agreement_date": "2024-01-01",
        "effective_date": None,
        "governing_law": None,
    }

    project_root = Path(__file__).resolve().parent.parent
    output_path = project_root / "outputs" / "sample_contract.json"

    save_contract(contract, output_path)

    print(f"Saved: {output_path}")
    print(f"Number of parties: {len(contract['parties'])}")
    for party in contract["parties"]:
        print(party)

    if contract["effective_date"] is None:
        print("Effective date is missing")

if __name__ == "__main__":
    main()