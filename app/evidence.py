"""Validate model values and locate exact quotations in source text."""

from datetime import date
import re

from app.schemas import (
    Evidence,
    Extraction,
    FieldStatus,
    ModelEvidence,
    ModelExtraction,
    ModelPartiesField,
    ModelScalarField,
    PartiesField,
    ScalarField,
)


def locate(quote: str, source: str) -> Evidence | None:
    if not quote or not quote.strip():
        return None
    start = source.find(quote)
    if start >= 0:
        end = start + len(quote)
        occurrences = source.count(quote)
    else:
        # CUAD text often has line breaks or repeated spaces inside a phrase.
        # Allow only whitespace variation; never accept changed words or punctuation.
        parts = quote.split()
        if not parts:
            return None
        pattern = re.compile(r"\s+".join(re.escape(part) for part in parts))
        matches = list(pattern.finditer(source))
        if not matches:
            return None
        start, end = matches[0].span()
        occurrences = len(matches)
    return Evidence(
        quote=source[start:end],
        start=start,
        end=end,
        page=None,
        occurrences=occurrences,
    )


def validate_quotes(quotes: list[ModelEvidence], source: str) -> tuple[list[Evidence], str | None]:
    evidence = []
    for item in quotes:
        located = locate(item.quote, source)
        if located is None:
            return [], "evidence_not_in_source"
        evidence.append(located)
    return evidence, None


def valid_date(value: str) -> bool:
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def scalar_field(field: ModelScalarField, source: str, *, is_date: bool = False) -> ScalarField:
    evidence, issue = validate_quotes(field.evidence, source)
    if issue is None:
        if field.status == "found" and (not field.value or not evidence):
            issue = "found_requires_value_and_evidence"
        elif field.status == "found" and is_date and not valid_date(field.value or ""):
            issue = "date_must_be_iso_calendar_date"
        elif field.status == "missing" and (field.value is not None or evidence):
            issue = "missing_requires_null_and_no_evidence"
        elif field.status == "ambiguous" and (field.value is not None or not evidence):
            issue = "ambiguous_requires_null_and_evidence"
    if issue:
        return ScalarField(status=FieldStatus.FAILED, value=None, evidence=[], issue=issue)
    return ScalarField(status=FieldStatus(field.status), value=field.value, evidence=evidence, issue=None)


def parties_field(field: ModelPartiesField, source: str) -> PartiesField:
    evidence, issue = validate_quotes(field.evidence, source)
    names = [name.strip() for name in field.value]
    if issue is None:
        if any(not name for name in names) or len({name.casefold() for name in names}) != len(names):
            issue = "parties_must_be_nonempty_and_unique"
        elif field.status == "found" and (not names or not evidence):
            issue = "found_requires_value_and_evidence"
        elif field.status == "missing" and (names or evidence):
            issue = "missing_requires_empty_values_and_evidence"
        elif field.status == "ambiguous" and (names or not evidence):
            issue = "ambiguous_requires_empty_values_and_evidence"
    if issue:
        return PartiesField(status=FieldStatus.FAILED, value=[], evidence=[], issue=issue)
    return PartiesField(status=FieldStatus(field.status), value=names, evidence=evidence, issue=None)


def validate_extraction(model: ModelExtraction, source: str) -> Extraction:
    return Extraction(
        document_name=scalar_field(model.document_name, source),
        parties=parties_field(model.parties, source),
        agreement_date=scalar_field(model.agreement_date, source, is_date=True),
        effective_date=scalar_field(model.effective_date, source, is_date=True),
        governing_law=scalar_field(model.governing_law, source),
    )
