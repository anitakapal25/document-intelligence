"""Private pilot API and small browser upload page."""

import hashlib
import json
import logging
import os
import tempfile
import time
from functools import lru_cache
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from app.budget import BudgetExceeded, actual_micro_usd, make_budget
from app.parsers import parse_pdf
from app.pdf_workflow import extract_parsed
from app.schemas import ExtractionRun, RunStatus


ROOT = Path(__file__).resolve().parent.parent
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
LOGGER = logging.getLogger(__name__)
app = FastAPI(title="Document Intelligence Pilot", version="0.6.0",
              description="Private CUAD/synthetic PDF extraction pilot")


@lru_cache(maxsize=1)
def allowed_pdfs() -> dict[str, str]:
    scope = os.getenv("PILOT_SCOPE", "development")
    if scope not in ("development", "demo"):
        raise RuntimeError("Unsupported PILOT_SCOPE")
    filename = "allowed_demo_pdfs.json" if scope == "demo" else "allowed_pdfs.json"
    path = ROOT / "configs" / filename
    data = json.loads(path.read_text(encoding="utf-8"))
    return {item["sha256"]: item["document_id"] for item in data["contracts"]}


@lru_cache(maxsize=1)
def get_budget():
    return make_budget()


def error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "document-intelligence-pilot"}


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    html = (ROOT / "app/static/upload.html").read_text(encoding="utf-8")
    return HTMLResponse(html, headers={"Cache-Control": "no-store",
                                       "X-Content-Type-Options": "nosniff"})


@app.get("/scope")
def scope() -> dict:
    return {"scope": os.getenv("PILOT_SCOPE", "development"),
            "documents": sorted(allowed_pdfs().values())}


@app.get("/sample.pdf")
def sample_pdf() -> FileResponse:
    return FileResponse(ROOT / "examples/sample_agreement.pdf", media_type="application/pdf",
                        filename="sample_agreement.pdf")


@app.post("/extract", response_model=ExtractionRun)
def extract(file: UploadFile = File(...), budget=Depends(get_budget)):
    if not file.filename or Path(file.filename).suffix.casefold() != ".pdf":
        raise error(415, "unsupported_file_type", "Upload a .pdf file")
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise error(415, "unsupported_media_type", "Upload a PDF with a PDF content type")
    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise error(413, "file_too_large", "PDF exceeds the 10 MiB limit")
    contents = file.file.read(MAX_UPLOAD_BYTES + 1)
    if not contents:
        raise error(422, "empty_file", "PDF is empty")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise error(413, "file_too_large", "PDF exceeds the 10 MiB limit")
    if not contents.startswith(b"%PDF-"):
        raise error(415, "invalid_pdf", "File does not have a PDF header")
    digest = hashlib.sha256(contents).hexdigest()
    document_id = allowed_pdfs().get(digest)
    if document_id is None:
        raise error(422, "outside_pilot_scope", "This private pilot accepts only its listed CUAD and synthetic PDFs")

    try:
        reservation = budget.reserve()
    except BudgetExceeded as exc:
        raise error(429, "monthly_budget_limit", str(exc)) from exc
    except Exception as exc:
        LOGGER.error("Budget reservation failed; error_type=%s", type(exc).__name__)
        raise error(503, "budget_unavailable", "Usage ledger is unavailable") from exc

    started = time.perf_counter()
    actual = None  # Unknown usage keeps the conservative reservation.
    try:
        with tempfile.TemporaryDirectory(prefix="document-intelligence-") as directory:
            path = Path(directory) / "contract.pdf"
            path.write_bytes(contents)
            try:
                parsed = parse_pdf(path, parser="docling")
            except ValueError as exc:
                actual = 0  # No model call has happened.
                raise error(422, "pdf_parse_failed", str(exc)) from exc
            except Exception as exc:
                actual = 0
                LOGGER.error("PDF parser failed; sha256=%s error_type=%s", digest, type(exc).__name__)
                raise error(502, "pdf_parse_failed", "PDF parser failed") from exc
            try:
                run = extract_parsed(document_id, parsed)
            except ValueError as exc:
                raise error(422, "document_not_processable", str(exc)) from exc
            except Exception as exc:
                LOGGER.error("Extraction failed; sha256=%s error_type=%s", digest, type(exc).__name__)
                raise error(502, "extraction_failed", "Extraction failed unexpectedly") from exc
        if run.extraction is None and run.error_code:
            if "model_refusal" in run.error_code or "content_filtered" in run.error_code:
                run = run.model_copy(update={"status": RunStatus.REFUSED})
            elif "model_incomplete" in run.error_code or "output_token_limit" in run.error_code:
                run = run.model_copy(update={"status": RunStatus.INCOMPLETE})
        if run.status == RunStatus.COMPLETED and (run.metadata.input_tokens or 0) > 0:
            actual = actual_micro_usd(run.metadata.model_dump())
        LOGGER.info("pdf_sha256=%s status=%s elapsed_ms=%d input_tokens=%s output_tokens=%s",
                    digest, run.status.value, round((time.perf_counter() - started) * 1000),
                    run.metadata.input_tokens, run.metadata.output_tokens)
        if run.status in (RunStatus.FAILED, RunStatus.REFUSED, RunStatus.INCOMPLETE):
            status = 422 if run.status == RunStatus.REFUSED else 502
            return JSONResponse(status_code=status, content=run.model_dump(mode="json"),
                                headers={"Cache-Control": "no-store"})
        return JSONResponse(content=run.model_dump(mode="json"),
                            headers={"Cache-Control": "no-store"})
    finally:
        try:
            budget.settle(reservation, actual)
        except Exception as exc:
            LOGGER.error("Budget settlement failed; reservation=%s error_type=%s",
                         reservation.token, type(exc).__name__)
