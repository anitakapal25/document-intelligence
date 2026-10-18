"""Score selected development runs and write a small-pilot Markdown report."""

import argparse
import hashlib
import json
from collections import Counter
from statistics import median
from pathlib import Path

from app.analytics import connect, estimated_openai_cost, save_run
from app.evaluation import FIELD_NAMES, aggregate, score_run


ROOT = Path(__file__).resolve().parent.parent


def fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def report_group(source: str, items: list[tuple[dict, dict]]) -> list[str]:
    scores = [score for _, score in items]
    totals = aggregate(scores)
    lines = [f"## {source} ({len(items)} contract run(s))", "",
             "| Type | Field | Ref found | Ref missing | Ambig./excluded | TP | FP | FN | Precision | Recall | F1 | Correct absent | False present | Absent abstained | Failures | Evidence ref support | Evidence token F1 (n) | Span IoU (n) |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for field, row in totals.items():
        excluded = row["reference_ambiguous"] + row["reference_unscorable"]
        field_type = {"Document Name": "name", "Parties": "entity set", "Agreement Date": "date",
                      "Effective Date": "date", "Governing Law": "jurisdiction"}[field]
        lines.append(
            f"| {field_type} | {field} | {row['reference_found']} | {row['reference_missing']} | {excluded} | "
            f"{row['tp']} | {row['fp']} | {row['fn']} | {fmt(row['precision'])} | "
            f"{fmt(row['recall'])} | {fmt(row['f1'])} | {row['correct_absent']} | "
            f"{row['absent_false_present']} | {row['absent_abstained']} | {row['processing_failures']} | {row['evidence_support']} | "
            f"{fmt(row['evidence_token_f1'])} ({row['evidence_scored']}) | "
            f"{fmt(row['evidence_span_iou'])} ({row['span_scored']}) |"
        )
    input_tokens = sum(run["metadata"].get("input_tokens") or 0 for run, _ in items)
    output_tokens = sum(run["metadata"].get("output_tokens") or 0 for run, _ in items)
    model_ms = sum(run["metadata"].get("elapsed_ms") or 0 for run, _ in items)
    latencies = sorted((run["metadata"].get("elapsed_ms") or 0) / 1000 for run, _ in items)
    p95 = latencies[max(0, (95 * len(latencies) + 99) // 100 - 1)]
    estimates = [estimated_openai_cost(run["metadata"]) for run, _ in items]
    statuses = Counter(run["status"] for run, _ in items)
    status_summary = ", ".join(f"{status} {count}" for status, count in sorted(statuses.items()))
    lines += ["", f"Run statuses: {status_summary}. "
              f"Usage: {input_tokens:,} input / {output_tokens:,} output tokens. "
              f"Recorded model-call time: {model_ms / 1000:.2f}s. "
              f"Per-run median/p95: {median(latencies):.2f}s/{p95:.2f}s. "
              f"Estimated OpenAI cost: ${sum(value or 0 for value in estimates):.5f} "
              f"({sum(value is not None for value in estimates)}/{len(estimates)} priced runs).", ""]
    return lines


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, action="append", default=[],
                        help="Saved run JSON; repeat for each development run")
    parser.add_argument("--all-development-text", action="store_true",
                        help="Add all current text-v2 development runs")
    args = parser.parse_args()
    references = json.loads((ROOT / "references/development.json").read_text(encoding="utf-8"))
    by_title = {item["title"]: item for item in references["contracts"]}
    paths = list(args.run)
    if args.all_development_text:
        for path in (ROOT / "outputs/text_runs").glob("*.json"):
            candidate = json.loads(path.read_text(encoding="utf-8"))
            if (candidate["document_id"] in by_title and
                    candidate["metadata"]["source"] == "cuad_supplied_text" and
                    candidate["metadata"]["prompt_version"] == "text-v2"):
                paths.append(path)
    if not paths:
        parser.error("provide --run or --all-development-text")
    training = json.loads((ROOT / "data/raw/cuad_benchmark/train_separate_questions.json").read_text(encoding="utf-8"))
    contexts = {item["title"]: [paragraph["context"] for paragraph in item["paragraphs"]]
                for item in training["data"]}
    groups = {}
    database = connect(ROOT / "data/processed/benchmark.duckdb")
    seen = set()
    for path in paths:
        content = path.read_bytes()
        run = json.loads(content)
        title = run["document_id"]
        if title not in by_title:
            parser.error(f"Run is not a selected development contract: {title}")
        identity = (title, run["metadata"]["source"], run["metadata"]["prompt_version"])
        if identity in seen:
            parser.error(f"Duplicate contract/source/prompt in selected runs: {identity}")
        seen.add(identity)
        score = score_run(run, by_title[title], contexts[title])
        run_id = hashlib.sha256(content).hexdigest()
        save_run(database, run_id, run, score)
        groups.setdefault(run["metadata"]["source"], []).append((run, score))
    database.close()
    lines = ["# Development pilot baseline", "",
             "The CUAD supplied-text section covers all 20 selected development contracts. The Docling section covers one matched development PDF. These are development results, not held-out or production accuracy estimates. Four CUAD-omitted date labels were manually added after reviewing model disagreements, so those metrics include post-run reference adjudication.", "",
             "Incorrect replacements count as both FP and FN. Missing references with missing predictions count as correct absent, outside precision/recall denominators. Ambiguous and unscorable references are excluded from value metrics. Processing/schema failures are counted separately, not silently scored as missing.", "",
             "Evidence token F1 is the best reference-span/predicted-quote pair. Character-span IoU is shown only for CUAD supplied text; PDF parser offsets cannot be aligned to CUAD offsets without a separate mapping. Evidence support and scored-pair counts differ when a prediction has no quotation.", ""]
    for source, items in sorted(groups.items(), key=lambda pair: pair[0] != "cuad_supplied_text"):
        lines.extend(report_group(source, items))
    lines += ["Estimated OpenAI cost uses the current short-context standard GPT-6 Luna list rates ($0.10/M input, $0.50/M output) without a cached-input discount. It excludes parser charges, tax, and other account costs. Recorded time sums model calls and excludes PDF parsing; end-to-end timing is a later instrumentation step.", ""]
    output = ROOT / "outputs/reports/development_baseline.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
