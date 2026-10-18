"""PDF parser adapters with explicit, one-based page provenance."""

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.config import load_local_secret


class ParsedPage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    number: int
    text: str


class ParsedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    parser: Literal["docling", "llamaparse"]
    pages: list[ParsedPage]


def parse_docling(path: Path) -> ParsedDocument:
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter(allowed_formats=[InputFormat.PDF])
    result = converter.convert(path)
    if result.status.value != "success":
        raise ValueError(f"Docling conversion status: {result.status.value}")
    document = result.document
    pages = [
        ParsedPage(number=number, text=document.export_to_text(page_no=number).strip())
        for number in sorted(document.pages)
    ]
    return ParsedDocument(parser="docling", pages=pages)


def parse_llamaparse(path: Path) -> ParsedDocument:
    """Comparison parser; requires a LlamaCloud account and API key."""
    from llama_cloud import LlamaCloud

    if not load_local_secret("LLAMA_CLOUD_API_KEY"):
        raise ValueError("LLAMA_CLOUD_API_KEY is required for LlamaParse")
    api_key = os.environ["LLAMA_CLOUD_API_KEY"]
    client = LlamaCloud(api_key=api_key)
    uploaded = client.files.create(file=path, purpose="parse")
    result = client.parsing.parse(file_id=uploaded.id, tier="cost_effective",
                                  version="2026-09-28", expand=["markdown"])
    if result.markdown is None:
        raise ValueError("LlamaParse returned no markdown pages")
    pages = []
    for page in result.markdown.pages:
        if not page.success:
            raise ValueError(f"LlamaParse failed page {getattr(page, 'page_number', '?')}")
        pages.append(ParsedPage(number=page.page_number, text=page.markdown.strip()))
    return ParsedDocument(parser="llamaparse", pages=pages)


def parse_pdf(path: Path, parser: Literal["docling", "llamaparse"] = "docling") -> ParsedDocument:
    if not path.is_file() or path.suffix.lower() != ".pdf":
        raise ValueError("Expected an existing PDF file")
    if parser == "docling":
        return parse_docling(path)
    if parser == "llamaparse":
        return parse_llamaparse(path)
    raise ValueError(f"Unknown parser: {parser}")
