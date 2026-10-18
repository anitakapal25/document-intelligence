"""Coordinate page-preserving LlamaIndex chunks and the existing extractor."""

from collections import defaultdict
from pathlib import Path
import re

from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter

from app.extractor import MODEL, PROMPT_VERSION, extract_text
from app.parsers import ParsedDocument, parse_pdf
from app.schemas import (
    Evidence, Extraction, ExtractionRun, FieldStatus, PartiesField, RunMetadata,
    RunStatus, ScalarField,
)


MAX_CHUNKS = 80


def page_chunks(parsed: ParsedDocument) -> list[tuple[int, str]]:
    """LlamaIndex manages document metadata and splitting; page stays attached."""
    splitter = SentenceSplitter(chunk_size=3000, chunk_overlap=200)
    chunks = []
    for page in parsed.pages:
        if not page.text.strip():
            continue
        document = Document(text=page.text, metadata={"page": page.number})
        for node in splitter.get_nodes_from_documents([document]):
            text = node.text.strip()
            if text:
                chunks.append((int(node.metadata["page"]), text))
    if not chunks:
        raise ValueError("PDF parser returned no extractable text")
    if len(chunks) > MAX_CHUNKS:
        raise ValueError(f"PDF needs {len(chunks)} chunks; limit is {MAX_CHUNKS}")
    return chunks


def _source_evidence(evidence: list[Evidence], page: int, page_text: str) -> list[Evidence]:
    mapped = []
    for item in evidence:
        start = page_text.find(item.quote)
        if start < 0:
            raise ValueError("Chunk quotation was not found in its source page")
        mapped.append(Evidence(
            quote=item.quote, start=start, end=start + len(item.quote),
            page=page, occurrences=page_text.count(item.quote),
        ))
    return mapped


def _merge_scalar(fields: list[ScalarField]) -> ScalarField:
    found = [field for field in fields if field.status == FieldStatus.FOUND]
    values = {field.value.casefold().strip() for field in found if field.value}
    if len(values) > 1:
        return ScalarField(status=FieldStatus.AMBIGUOUS, value=None,
                           evidence=[e for field in found for e in field.evidence], issue="conflicting_chunk_values")
    if found:
        return ScalarField(status=FieldStatus.FOUND, value=found[0].value,
                           evidence=[e for field in found for e in field.evidence], issue=None)
    ambiguous = [field for field in fields if field.status == FieldStatus.AMBIGUOUS]
    if ambiguous:
        return ScalarField(status=FieldStatus.AMBIGUOUS, value=None,
                           evidence=[e for field in ambiguous for e in field.evidence], issue=None)
    if any(field.status == FieldStatus.FAILED for field in fields):
        return ScalarField(status=FieldStatus.FAILED, value=None, evidence=[], issue="chunk_failed")
    return ScalarField(status=FieldStatus.MISSING, value=None, evidence=[], issue=None)


def _merge_parties(fields: list[PartiesField]) -> PartiesField:
    names = {}
    evidence = []
    for field in fields:
        if field.status == FieldStatus.FOUND:
            for name in field.value:
                normalized = re.sub(r"[^a-z0-9]", "", name.casefold())
                names.setdefault(normalized, name)
            evidence.extend(field.evidence)
    if names:
        return PartiesField(status=FieldStatus.FOUND, value=list(names.values()), evidence=evidence, issue=None)
    ambiguous = [field for field in fields if field.status == FieldStatus.AMBIGUOUS]
    if ambiguous:
        return PartiesField(status=FieldStatus.AMBIGUOUS, value=[],
                            evidence=[e for field in ambiguous for e in field.evidence], issue=None)
    if any(field.status == FieldStatus.FAILED for field in fields):
        return PartiesField(status=FieldStatus.FAILED, value=[], evidence=[], issue="chunk_failed")
    return PartiesField(status=FieldStatus.MISSING, value=[], evidence=[], issue=None)


def extract_parsed(document_id: str, parsed: ParsedDocument, *, client=None) -> ExtractionRun:
    chunks = page_chunks(parsed)
    page_texts = {page.number: page.text for page in parsed.pages}
    results = defaultdict(list)
    input_tokens = output_tokens = elapsed_ms = 0
    errors = []
    for index, (page, text) in enumerate(chunks):
        run = extract_text(f"{document_id}:chunk-{index}", text, client=client)
        input_tokens += run.metadata.input_tokens or 0
        output_tokens += run.metadata.output_tokens or 0
        elapsed_ms += run.metadata.elapsed_ms
        if run.extraction is None:
            errors.append(run.error_code or run.status.value)
            continue
        for name in Extraction.model_fields:
            field = getattr(run.extraction, name).model_copy(deep=True)
            field.evidence = _source_evidence(field.evidence, page, page_texts[page])
            results[name].append(field)
    metadata = RunMetadata(model=MODEL, source=f"pdf:{parsed.parser}", prompt_version=PROMPT_VERSION,
                           elapsed_ms=elapsed_ms, input_tokens=input_tokens,
                           output_tokens=output_tokens, response_id=None)
    if not any(results.values()):
        return ExtractionRun(document_id=document_id, status=RunStatus.FAILED,
                             extraction=None, metadata=metadata,
                             error_code=";".join(sorted(set(errors))) or "no_chunk_results")
    extraction = Extraction(
        document_name=_merge_scalar(results["document_name"]),
        parties=_merge_parties(results["parties"]),
        agreement_date=_merge_scalar(results["agreement_date"]),
        effective_date=_merge_scalar(results["effective_date"]),
        governing_law=_merge_scalar(results["governing_law"]),
    )
    has_failure = bool(errors) or any(getattr(extraction, name).status == FieldStatus.FAILED
                                      for name in Extraction.model_fields)
    return ExtractionRun(document_id=document_id,
                         status=RunStatus.PARTIAL if has_failure else RunStatus.COMPLETED,
                         extraction=extraction, metadata=metadata,
                         error_code=";".join(sorted(set(errors))) if errors else None)


def extract_pdf(path: Path, *, parser: str = "docling", client=None) -> ExtractionRun:
    parsed = parse_pdf(path, parser=parser)
    return extract_parsed(path.stem, parsed, client=client)
