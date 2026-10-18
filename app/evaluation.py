"""Pilot field and evidence scoring against reviewed CUAD references."""

import re
from collections import Counter
from datetime import date


FIELD_NAMES = {
    "Document Name": "document_name",
    "Parties": "parties",
    "Agreement Date": "agreement_date",
    "Effective Date": "effective_date",
    "Governing Law": "governing_law",
}
US_STATES = {"california", "illinois", "kansas", "massachusetts", "new york", "texas", "washington"}


def normalize_name(value: str) -> str:
    return " ".join(value.casefold().split())


def normalize_party(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def normalize_date(value: str) -> str | None:
    try:
        return date.fromisoformat(value).isoformat() if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) else None
    except ValueError:
        return None


def normalize_jurisdiction(value: str) -> str | None:
    text = " ".join(value.casefold().replace(".", "").replace(",", " ").split())
    text = re.sub(r"^(?:the )?(?:laws? of )?(?:the )?(?:state of )?", "", text)
    text = re.sub(r"\s+(?:law|laws)$", "", text)
    text = re.sub(r"\s+(?:us|usa|united states)$", "", text).strip()
    if text in US_STATES:
        return f"{text}, us"
    return {
        "english": "england and wales", "england": "england and wales",
        "england and wales": "england and wales", "china": "china (prc)",
        "prc": "china (prc)", "china (prc)": "china (prc)",
        "people's republic of china": "china (prc)",
        "germany": "germany", "federal republic of germany": "germany",
        "israel": "israel",
    }.get(text)


def normalize_value(field: str, value: str) -> str | None:
    if field == "Document Name":
        return normalize_name(value)
    if field in ("Agreement Date", "Effective Date"):
        return normalize_date(value)
    if field == "Governing Law":
        return normalize_jurisdiction(value)
    raise ValueError(field)


def token_f1(a: str, b: str) -> float:
    left = Counter(re.findall(r"\w+", a.casefold()))
    right = Counter(re.findall(r"\w+", b.casefold()))
    if not left or not right:
        return 0.0
    common = sum((left & right).values())
    return 2 * common / (sum(left.values()) + sum(right.values()))


def span_iou(start_a: int, end_a: int, start_b: int, end_b: int) -> float:
    overlap = max(0, min(end_a, end_b) - max(start_a, start_b))
    union = max(end_a, end_b) - min(start_a, start_b)
    return overlap / union if union else 0.0


def _reference_quotes(reference: dict, contexts: list[str]) -> list[tuple[str, dict]]:
    quotes = []
    for span in reference.get("source_spans", []):
        text = contexts[span["paragraph"]][span["start"]:span["end"]]
        quotes.append((text, span))
    return quotes


def score_field(field: str, reference: dict, prediction: dict | None,
                contexts: list[str], *, source_type: str) -> dict:
    ref_status = reference["status"]
    pred_status = prediction["status"] if prediction else "processing_failed"
    ref_value = reference.get("value")
    pred_value = prediction.get("value") if prediction else None
    result = {
        "reference_status": ref_status, "prediction_status": pred_status,
        "tp": 0, "fp": 0, "fn": 0, "correct_absent": 0,
        "scorable": ref_status in ("found", "missing"),
        "evidence_token_f1": None, "evidence_span_iou": None,
        "evidence_support": bool(reference.get("source_spans")),
    }
    quotes = _reference_quotes(reference, contexts)
    evidence = prediction.get("evidence", []) if prediction else []
    if quotes and evidence:
        result["evidence_token_f1"] = max(
            token_f1(ref_quote, item["quote"]) for ref_quote, _ in quotes for item in evidence
        )
        if source_type == "cuad_supplied_text":
            # CUAD offsets are paragraph-relative; the extractor joins contexts with two newlines.
            offsets = []
            cursor = 0
            for context in contexts:
                offsets.append(cursor)
                cursor += len(context) + 2
            result["evidence_span_iou"] = max(
                span_iou(offsets[span["paragraph"]] + span["start"],
                         offsets[span["paragraph"]] + span["end"], item["start"], item["end"])
                for _, span in quotes for item in evidence
            )
    if not result["scorable"]:
        return result
    if pred_status in ("failed", "processing_failed"):
        return result  # Count separately as processing/schema failure, never as a true negative.

    if field == "Parties":
        expected = [normalize_party(name) for name in (ref_value or [])]
        actual = [normalize_party(name) for name in (pred_value or [])] if pred_status == "found" else []
        unused = Counter(expected)
        for name in actual:
            if unused[name]:
                result["tp"] += 1
                unused[name] -= 1
            else:
                result["fp"] += 1
        result["fn"] = sum(unused.values())
    else:
        expected = normalize_value(field, ref_value) if ref_status == "found" and ref_value else None
        actual = normalize_value(field, pred_value) if pred_status == "found" and pred_value else None
        if pred_status == "found":
            if actual is not None and actual == expected:
                result["tp"] = 1
            else:
                result["fp"] = 1
                if expected is not None:
                    result["fn"] = 1
        elif expected is not None:
            result["fn"] = 1
    if ref_status == "missing" and pred_status == "missing":
        result["correct_absent"] = 1

    return result


def score_run(run: dict, reference: dict, contexts: list[str]) -> dict[str, dict]:
    extraction = run.get("extraction") or {}
    return {
        field: score_field(field, reference["fields"][field], extraction.get(key), contexts,
                           source_type=run["metadata"]["source"])
        for field, key in FIELD_NAMES.items()
    }


def aggregate(scores: list[dict[str, dict]]) -> dict[str, dict]:
    summary = {}
    for field in FIELD_NAMES:
        rows = [score[field] for score in scores]
        tp, fp, fn = (sum(row[key] for row in rows) for key in ("tp", "fp", "fn"))
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / (tp + fn) if tp + fn else None
        token = [row["evidence_token_f1"] for row in rows if row["evidence_token_f1"] is not None]
        span = [row["evidence_span_iou"] for row in rows if row["evidence_span_iou"] is not None]
        summary[field] = {
            "tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall,
            "f1": (2 * precision * recall / (precision + recall) if precision + recall else 0.0)
            if precision is not None and recall is not None else None,
            "reference_found": sum(row["reference_status"] == "found" for row in rows),
            "reference_missing": sum(row["reference_status"] == "missing" for row in rows),
            "reference_ambiguous": sum(row["reference_status"] == "ambiguous" for row in rows),
            "reference_unscorable": sum(row["reference_status"] == "unscorable" for row in rows),
            "correct_absent": sum(row["correct_absent"] for row in rows),
            "absent_false_present": sum(row["reference_status"] == "missing" and row["prediction_status"] == "found" for row in rows),
            "absent_abstained": sum(row["reference_status"] == "missing" and row["prediction_status"] == "ambiguous" for row in rows),
            "processing_failures": sum(row["prediction_status"] in ("failed", "processing_failed") for row in rows),
            "evidence_support": sum(row["evidence_support"] for row in rows),
            "evidence_scored": len(token), "evidence_token_f1": sum(token) / len(token) if token else None,
            "span_scored": len(span), "evidence_span_iou": sum(span) / len(span) if span else None,
        }
    return summary
