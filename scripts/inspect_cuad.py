import json
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: inspect_cuad.py <path-to-training-json>")

    input_path = Path(sys.argv[1])

    with input_path.open(encoding="utf-8") as file:
        dataset = json.load(file)

    print("Top-level keys:", list(dataset))
    print("Contract records:", len(dataset["data"]))

    contract = dataset["data"][1]
    print("Contract title:", contract["title"])

    paragraph = contract["paragraphs"][0]
    context = paragraph["context"]

    print("Context characters:", len(context))
    print("Context preview:", repr(context[:300]))

    for qa in paragraph["qas"]:
        print("\nID:", qa["id"])
        print("Question:", qa["question"])
        print("Impossible:", qa.get("is_impossible"))
        print("Answers:", qa["answers"])

        for answer in qa["answers"]:
            start = answer["answer_start"]
            text = answer["text"]
            source_span = context[start:start + len(text)]
            print("Span matches source:", source_span == text)


if __name__ == "__main__":
    main()