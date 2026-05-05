from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from docchecker.core.config import get_settings
from docchecker.domain.document import UploadedDocumentRecord
from docchecker.domain.enums import DraftRuleSetStatus, SourceType, TaskStatus
from docchecker.domain.findings import CheckReport
from docchecker.domain.requirements import RequirementDocument, RequirementDocumentModel
from docchecker.domain.rules import (
    DraftRuleSet,
    ExtractionSummary,
    FormatRule,
    RuleSet,
    UnsupportedRequirement,
)
from docchecker.domain.tasks import CheckTask
from docchecker.services.check_service import CheckService
from docchecker.services.docx_validator import DocumentValidationError
from docchecker.services.file_storage import LocalFileStorage
from docchecker.services.requirement_parser import parse_requirement_document
from docchecker.services.rule_extractor import (
    RuleExtractionConfigurationError,
    extract_rules_from_requirement_document,
    extract_rules_from_text,
)
from docchecker.services.state_store import SqliteStateStore
from docchecker.services.word_document_preparer import prepare_word_document

settings = get_settings()
storage = LocalFileStorage(settings.storage_dir)
state_store = SqliteStateStore(settings.database_path)
state_store.initialize()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    state_store.initialize()
    yield


app = FastAPI(title="DocChecker API", version="0.1.0", lifespan=lifespan)


class UploadedDocumentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    filename: str
    size_bytes: int
    original_format: str
    normalized_format: str


class CreateCheckTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    ruleset_id: str


class UpdateRuleSetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("模板名称不能为空。")
        return name


class CreateDraftRuleSetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    source_type: SourceType
    manual_text: str | None = None
    requirement_document_id: str | None = None
    template_ruleset_id: str | None = None

    @model_validator(mode="after")
    def validate_source_payload(self) -> "CreateDraftRuleSetRequest":
        if self.source_type == SourceType.manual and not (self.manual_text or "").strip():
            raise ValueError("手动输入规则来源必须提供 manual_text。")
        if self.source_type == SourceType.requirement_doc and not self.requirement_document_id:
            raise ValueError("规范文档规则来源必须提供 requirement_document_id。")
        if self.source_type == SourceType.template and not self.template_ruleset_id:
            raise ValueError("模板规则来源必须提供 template_ruleset_id。")
        return self


class UpdateDraftRuleSetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rules: list[FormatRule]
    suggested_rules: list[FormatRule] | None = None
    name: str | None = None
    parse_warnings: list[str] | None = None


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "time": datetime.now(UTC).isoformat()}


UploadWordFile = Annotated[UploadFile, File(...)]


@app.post("/api/documents", response_model=UploadedDocumentResponse)
async def upload_document(file: UploadWordFile) -> UploadedDocumentResponse:
    stored = None
    try:
        stored = await storage.save_upload(file, max_size_bytes=settings.max_document_size_bytes)
        prepared = prepare_word_document(
            stored.path,
            max_size_bytes=settings.max_document_size_bytes,
            libreoffice_command=settings.libreoffice_command,
            conversion_timeout_seconds=settings.libreoffice_conversion_timeout_seconds,
        )
    except DocumentValidationError as exc:
        if stored is not None:
            _cleanup_failed_upload(stored.path)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record = UploadedDocumentRecord(
        id=stored.document_id,
        filename=stored.original_filename,
        path=str(prepared.normalized_path),
        original_path=str(prepared.original_path),
        original_format=prepared.original_format,
        normalized_format=prepared.normalized_format,
        size_bytes=stored.path.stat().st_size,
    )
    try:
        state_store.save_document(record)
    except Exception:
        _cleanup_failed_upload(stored.path)
        raise
    return UploadedDocumentResponse(
        document_id=stored.document_id,
        filename=stored.original_filename,
        size_bytes=record.size_bytes,
        original_format=prepared.original_format,
        normalized_format=prepared.normalized_format,
    )


@app.post("/api/requirement-documents", response_model=RequirementDocument)
async def upload_requirement_document(file: UploadWordFile) -> RequirementDocument:
    stored = None
    try:
        stored = await storage.save_upload(file, max_size_bytes=settings.max_requirement_size_bytes)
        prepared = prepare_word_document(
            stored.path,
            max_size_bytes=settings.max_requirement_size_bytes,
            libreoffice_command=settings.libreoffice_command,
            conversion_timeout_seconds=settings.libreoffice_conversion_timeout_seconds,
        )
        parsed_requirement = parse_requirement_document(prepared.normalized_path)
        extracted_text = "\n".join(
            f"{block.location}\t{block.text}" for block in parsed_requirement.blocks if block.text
        )
    except DocumentValidationError as exc:
        if stored is not None:
            _cleanup_failed_upload(stored.path)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    requirement_document = RequirementDocument(
        id=f"req_{uuid4().hex}",
        filename=stored.original_filename,
        path=str(prepared.normalized_path),
        size_bytes=stored.path.stat().st_size,
        extracted_text=extracted_text,
        blocks=parsed_requirement.blocks,
        original_format=prepared.original_format,
        normalized_format=prepared.normalized_format,
        created_at=_now(),
    )
    try:
        state_store.save_requirement_document(requirement_document)
    except Exception:
        _cleanup_failed_upload(stored.path)
        raise
    return requirement_document


@app.post("/api/rulesets", response_model=RuleSet)
def create_ruleset(ruleset: RuleSet) -> RuleSet:
    state_store.save_ruleset(ruleset)
    return ruleset


@app.get("/api/rulesets", response_model=list[RuleSet])
def list_rulesets() -> list[RuleSet]:
    return state_store.list_rulesets()


@app.patch("/api/rulesets/{ruleset_id}", response_model=RuleSet)
def update_ruleset(ruleset_id: str, request: UpdateRuleSetRequest) -> RuleSet:
    ruleset = state_store.get_ruleset(ruleset_id)
    if not ruleset:
        raise HTTPException(status_code=404, detail="规则集不存在。")
    updated = ruleset.model_copy(update={"name": request.name}, deep=True)
    state_store.save_ruleset(updated)
    return updated


@app.delete("/api/rulesets/{ruleset_id}")
def delete_ruleset(ruleset_id: str) -> dict[str, bool | str]:
    if not state_store.delete_ruleset(ruleset_id):
        raise HTTPException(status_code=404, detail="规则集不存在。")
    return {"id": ruleset_id, "deleted": True}


@app.post("/api/draft-rulesets", response_model=DraftRuleSet)
def create_draft_ruleset(request: CreateDraftRuleSetRequest) -> DraftRuleSet:
    document = state_store.get_document(request.document_id)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在。")

    now = _now()
    if request.source_type == SourceType.template:
        template = state_store.get_ruleset(request.template_ruleset_id or "")
        if not template:
            raise HTTPException(status_code=404, detail="模板规则集不存在。")
        rules = [rule.model_copy(deep=True) for rule in template.rules]
        suggested_rules: list[FormatRule] = []
        warnings: list[str] = []
        extraction_summary = ExtractionSummary(structured_rules=len(rules))
        unsupported_requirements: list[UnsupportedRequirement] = []
        name = f"{template.name} 副本"
    else:
        text = request.manual_text or ""
        if request.source_type == SourceType.requirement_doc:
            requirement_document = state_store.get_requirement_document(
                request.requirement_document_id or ""
            )
            if not requirement_document:
                raise HTTPException(status_code=404, detail="规范文档不存在。")
            text = requirement_document.extracted_text
        try:
            if request.source_type == SourceType.requirement_doc:
                result = extract_rules_from_requirement_document(
                    RequirementDocumentModel(
                        source_filename=requirement_document.filename,
                        blocks=requirement_document.blocks,
                        markdown=requirement_document.extracted_text,
                    ),
                    source_type=request.source_type,
                )
            else:
                result = extract_rules_from_text(text, source_type=request.source_type)
        except RuleExtractionConfigurationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        rules = result.rules
        suggested_rules = result.suggested_rules
        warnings = result.parse_warnings
        extraction_summary = result.extraction_summary
        unsupported_requirements = result.unsupported_requirements
        extraction_trace = result.extraction_trace
        name = "候选规则集"

    draft = DraftRuleSet(
        id=f"draft_{uuid4().hex}",
        name=name,
        document_id=request.document_id,
        source_type=request.source_type,
        rules=rules,
        suggested_rules=suggested_rules,
        parse_warnings=warnings,
        extraction_summary=extraction_summary,
        unsupported_requirements=unsupported_requirements,
        extraction_trace=extraction_trace if request.source_type != SourceType.template else None,
        created_at=now,
        updated_at=now,
    )
    state_store.save_draft_ruleset(draft)
    return draft


@app.get("/api/draft-rulesets/{draft_id}", response_model=DraftRuleSet)
def get_draft_ruleset(draft_id: str) -> DraftRuleSet:
    draft = state_store.get_draft_ruleset(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="候选规则集不存在。")
    return draft


@app.patch("/api/draft-rulesets/{draft_id}", response_model=DraftRuleSet)
def update_draft_ruleset(draft_id: str, request: UpdateDraftRuleSetRequest) -> DraftRuleSet:
    draft = get_draft_ruleset(draft_id)
    if draft.status == DraftRuleSetStatus.published:
        raise HTTPException(status_code=400, detail="已发布的候选规则集不能继续编辑。")
    updated = draft.model_copy(
        update={
            "name": request.name or draft.name,
            "rules": request.rules,
            "suggested_rules": request.suggested_rules
            if request.suggested_rules is not None
            else draft.suggested_rules,
            "parse_warnings": request.parse_warnings
            if request.parse_warnings is not None
            else draft.parse_warnings,
            "updated_at": _now(),
        },
        deep=True,
    )
    state_store.save_draft_ruleset(updated)
    return updated


@app.post("/api/draft-rulesets/{draft_id}/publish", response_model=RuleSet)
def publish_draft_ruleset(draft_id: str) -> RuleSet:
    draft = get_draft_ruleset(draft_id)
    ruleset = RuleSet(
        id=f"ruleset_{uuid4().hex}",
        name=draft.name,
        source_type=draft.source_type,
        version=draft.version,
        locale=draft.locale,
        rules=[rule.model_copy(deep=True) for rule in draft.rules],
        created_at=_now(),
    )
    published_draft = draft.model_copy(
        update={
            "status": DraftRuleSetStatus.published,
            "published_ruleset_id": ruleset.id,
            "updated_at": _now(),
        }
    )
    state_store.save_many(
        [
            ("ruleset", ruleset.id, ruleset),
            ("draft_ruleset", draft_id, published_draft),
        ]
    )
    return ruleset


@app.post("/api/check-tasks", response_model=CheckTask)
def create_check_task(request: CreateCheckTaskRequest) -> CheckTask:
    document = state_store.get_document(request.document_id)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在。")
    ruleset = state_store.get_ruleset(request.ruleset_id)
    if not ruleset:
        raise HTTPException(status_code=404, detail="规则集不存在。")
    task = CheckTask(
        id=f"task_{uuid4().hex}",
        document_id=request.document_id,
        ruleset_id=request.ruleset_id,
        status=TaskStatus.running,
        created_at=_now(),
        updated_at=_now(),
    )
    state_store.save_check_task(task)
    service = CheckService(settings, storage)
    try:
        report = service.check_document(
            Path(document.path),
            document_id=request.document_id,
            filename=document.filename,
            ruleset=ruleset,
        )
    except DocumentValidationError as exc:
        failed = task.model_copy(
            update={"status": TaskStatus.failed, "error": str(exc), "updated_at": _now()}
        )
        state_store.save_check_task(failed)
        return failed
    except Exception as exc:
        failed = task.model_copy(
            update={"status": TaskStatus.failed, "error": str(exc), "updated_at": _now()}
        )
        state_store.save_check_task(failed)
        return failed
    succeeded = task.model_copy(
        update={"status": TaskStatus.succeeded, "report_id": report.id, "updated_at": _now()}
    )
    try:
        state_store.save_many(
            [
                ("report", report.id, report),
                ("check_task", task.id, succeeded),
            ]
        )
    except Exception as exc:
        storage.report_path(report.id).unlink(missing_ok=True)
        failed = task.model_copy(
            update={"status": TaskStatus.failed, "error": str(exc), "updated_at": _now()}
        )
        state_store.save_check_task(failed)
        return failed
    return succeeded


@app.get("/api/check-tasks", response_model=list[CheckTask])
def list_check_tasks() -> list[CheckTask]:
    return state_store.list_check_tasks()


@app.get("/api/check-tasks/{task_id}", response_model=CheckTask)
def get_check_task(task_id: str) -> CheckTask:
    task = state_store.get_check_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="检查任务不存在。")
    return task


@app.delete("/api/check-tasks/{task_id}")
def delete_check_task(task_id: str) -> dict[str, bool | str]:
    task = state_store.get_check_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="检查任务不存在。")
    if task.report_id:
        state_store.delete_report(task.report_id)
        storage.report_path(task.report_id).unlink(missing_ok=True)
    state_store.delete_check_task(task_id)
    return {"id": task_id, "deleted": True}


@app.get("/api/reports/{report_id}", response_model=CheckReport)
def get_report(report_id: str) -> CheckReport:
    report = state_store.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在。")
    return report


@app.get("/api/reports/{report_id}/export")
def export_report(report_id: str) -> dict[str, str]:
    path = storage.report_path(report_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="报告文件不存在。")
    return {"format": "markdown", "path": str(path), "content": path.read_text(encoding="utf-8")}


def _cleanup_failed_upload(path: Path) -> None:
    path.unlink(missing_ok=True)
    if path.suffix.lower() == ".doc":
        path.with_suffix(".docx").unlink(missing_ok=True)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def run() -> None:
    uvicorn.run("docchecker.api.main:app", host="127.0.0.1", port=8001, reload=True)
