from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict

from docchecker.core.config import get_settings
from docchecker.domain.findings import CheckReport
from docchecker.domain.rules import RuleSet
from docchecker.services.check_service import CheckService
from docchecker.services.docx_validator import DocumentValidationError, validate_docx_path
from docchecker.services.file_storage import LocalFileStorage

app = FastAPI(title="DocChecker API", version="0.1.0")
settings = get_settings()
storage = LocalFileStorage(settings.storage_dir)

DOCUMENTS: dict[str, dict[str, str]] = {}
RULESETS: dict[str, RuleSet] = {}
REPORTS: dict[str, CheckReport] = {}


class UploadedDocumentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    filename: str
    size_bytes: int


class CreateCheckTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    ruleset_id: str


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "time": datetime.now(UTC).isoformat()}


UploadDocxFile = Annotated[UploadFile, File(...)]


@app.post("/api/documents", response_model=UploadedDocumentResponse)
async def upload_document(file: UploadDocxFile) -> UploadedDocumentResponse:
    stored = await storage.save_upload(file)
    try:
        validate_docx_path(stored.path, max_size_bytes=settings.max_document_size_bytes)
    except DocumentValidationError as exc:
        stored.path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    DOCUMENTS[stored.document_id] = {
        "filename": stored.original_filename,
        "path": str(stored.path),
    }
    return UploadedDocumentResponse(
        document_id=stored.document_id,
        filename=stored.original_filename,
        size_bytes=stored.path.stat().st_size,
    )


@app.post("/api/rulesets", response_model=RuleSet)
def create_ruleset(ruleset: RuleSet) -> RuleSet:
    RULESETS[ruleset.id] = ruleset
    return ruleset


@app.get("/api/rulesets", response_model=list[RuleSet])
def list_rulesets() -> list[RuleSet]:
    return list(RULESETS.values())


@app.post("/api/check-tasks", response_model=CheckReport)
def create_check_task(request: CreateCheckTaskRequest) -> CheckReport:
    document = DOCUMENTS.get(request.document_id)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在。")
    ruleset = RULESETS.get(request.ruleset_id)
    if not ruleset:
        raise HTTPException(status_code=404, detail="规则集不存在。")
    service = CheckService(settings, storage)
    try:
        report = service.check_document(
            Path(document["path"]),
            document_id=request.document_id,
            filename=document["filename"],
            ruleset=ruleset,
        )
    except DocumentValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    REPORTS[report.id] = report
    return report


@app.get("/api/reports/{report_id}", response_model=CheckReport)
def get_report(report_id: str) -> CheckReport:
    report = REPORTS.get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在。")
    return report


@app.get("/api/reports/{report_id}/export")
def export_report(report_id: str) -> dict[str, str]:
    path = storage.report_path(report_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="报告文件不存在。")
    return {"format": "markdown", "path": str(path), "content": path.read_text(encoding="utf-8")}


def run() -> None:
    uvicorn.run("docchecker.api.main:app", host="127.0.0.1", port=8000, reload=True)
