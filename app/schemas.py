"""Structured model response and validated application response."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ModelEvidence(StrictModel):
    quote: str


class ModelScalarField(StrictModel):
    status: Literal["found", "missing", "ambiguous"]
    value: str | None
    evidence: list[ModelEvidence]


class ModelPartiesField(StrictModel):
    status: Literal["found", "missing", "ambiguous"]
    value: list[str]
    evidence: list[ModelEvidence]


class ModelExtraction(StrictModel):
    document_name: ModelScalarField
    parties: ModelPartiesField
    agreement_date: ModelScalarField
    effective_date: ModelScalarField
    governing_law: ModelScalarField


class FieldStatus(str, Enum):
    FOUND = "found"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    FAILED = "failed"


class RunStatus(str, Enum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    REFUSED = "refused"
    INCOMPLETE = "incomplete"


class Evidence(StrictModel):
    quote: str
    start: int
    end: int
    page: int | None
    occurrences: int


class ScalarField(StrictModel):
    status: FieldStatus
    value: str | None
    evidence: list[Evidence]
    issue: str | None


class PartiesField(StrictModel):
    status: FieldStatus
    value: list[str]
    evidence: list[Evidence]
    issue: str | None


class Extraction(StrictModel):
    document_name: ScalarField
    parties: PartiesField
    agreement_date: ScalarField
    effective_date: ScalarField
    governing_law: ScalarField


class RunMetadata(StrictModel):
    model: str
    source: str
    prompt_version: str
    elapsed_ms: int
    input_tokens: int | None
    output_tokens: int | None
    response_id: str | None


class ExtractionRun(StrictModel):
    document_id: str
    status: RunStatus
    extraction: Extraction | None
    metadata: RunMetadata
    error_code: str | None
