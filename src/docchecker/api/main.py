from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, model_validator

from docchecker.core.config import get_settings
from docchecker.domain.enums import DraftRuleSetStatus, SourceType, TaskStatus
from docchecker.domain.findings import CheckReport
from docchecker.domain.requirements import RequirementDocument
from docchecker.domain.rules import DraftRuleSet, FormatRule, RuleSet
from docchecker.domain.tasks import CheckTask
from docchecker.services.check_service import CheckService
from docchecker.services.docx_validator import DocumentValidationError, validate_docx_path
from docchecker.services.file_storage import LocalFileStorage
from docchecker.services.requirement_parser import extract_requirement_text
from docchecker.services.rule_extractor import extract_rules_from_text

app = FastAPI(title="DocChecker API", version="0.1.0")
settings = get_settings()
storage = LocalFileStorage(settings.storage_dir)

DOCUMENTS: dict[str, dict[str, str]] = {}
REQUIREMENT_DOCUMENTS: dict[str, RequirementDocument] = {}
RULESETS: dict[str, RuleSet] = {}
DRAFT_RULESETS: dict[str, DraftRuleSet] = {}
CHECK_TASKS: dict[str, CheckTask] = {}
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
    name: str | None = None
    parse_warnings: list[str] | None = None


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


@app.post("/api/requirement-documents", response_model=RequirementDocument)
async def upload_requirement_document(file: UploadDocxFile) -> RequirementDocument:
    stored = await storage.save_upload(file)
    try:
        validate_docx_path(stored.path, max_size_bytes=settings.max_requirement_size_bytes)
        extracted_text = extract_requirement_text(stored.path)
    except DocumentValidationError as exc:
        stored.path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    requirement_document = RequirementDocument(
        id=f"req_{uuid4().hex}",
        filename=stored.original_filename,
        path=str(stored.path),
        size_bytes=stored.path.stat().st_size,
        extracted_text=extracted_text,
        created_at=_now(),
    )
    REQUIREMENT_DOCUMENTS[requirement_document.id] = requirement_document
    return requirement_document


@app.post("/api/rulesets", response_model=RuleSet)
def create_ruleset(ruleset: RuleSet) -> RuleSet:
    RULESETS[ruleset.id] = ruleset
    return ruleset


@app.get("/api/rulesets", response_model=list[RuleSet])
def list_rulesets() -> list[RuleSet]:
    return list(RULESETS.values())


@app.post("/api/draft-rulesets", response_model=DraftRuleSet)
def create_draft_ruleset(request: CreateDraftRuleSetRequest) -> DraftRuleSet:
    if request.document_id not in DOCUMENTS:
        raise HTTPException(status_code=404, detail="文档不存在。")

    now = _now()
    if request.source_type == SourceType.template:
        template = RULESETS.get(request.template_ruleset_id or "")
        if not template:
            raise HTTPException(status_code=404, detail="模板规则集不存在。")
        rules = [rule.model_copy(deep=True) for rule in template.rules]
        warnings: list[str] = []
        name = f"{template.name} 副本"
    else:
        text = request.manual_text or ""
        if request.source_type == SourceType.requirement_doc:
            requirement_document = REQUIREMENT_DOCUMENTS.get(request.requirement_document_id or "")
            if not requirement_document:
                raise HTTPException(status_code=404, detail="规范文档不存在。")
            text = requirement_document.extracted_text
        result = extract_rules_from_text(text, source_type=request.source_type)
        rules = result.rules
        warnings = result.parse_warnings
        name = "候选规则集"

    draft = DraftRuleSet(
        id=f"draft_{uuid4().hex}",
        name=name,
        document_id=request.document_id,
        source_type=request.source_type,
        rules=rules,
        parse_warnings=warnings,
        created_at=now,
        updated_at=now,
    )
    DRAFT_RULESETS[draft.id] = draft
    return draft


@app.get("/api/draft-rulesets/{draft_id}", response_model=DraftRuleSet)
def get_draft_ruleset(draft_id: str) -> DraftRuleSet:
    draft = DRAFT_RULESETS.get(draft_id)
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
            "parse_warnings": request.parse_warnings
            if request.parse_warnings is not None
            else draft.parse_warnings,
            "updated_at": _now(),
        },
        deep=True,
    )
    DRAFT_RULESETS[draft_id] = updated
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
    RULESETS[ruleset.id] = ruleset
    DRAFT_RULESETS[draft_id] = draft.model_copy(
        update={
            "status": DraftRuleSetStatus.published,
            "published_ruleset_id": ruleset.id,
            "updated_at": _now(),
        }
    )
    return ruleset


@app.post("/api/check-tasks", response_model=CheckTask)
def create_check_task(request: CreateCheckTaskRequest) -> CheckTask:
    document = DOCUMENTS.get(request.document_id)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在。")
    ruleset = RULESETS.get(request.ruleset_id)
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
    CHECK_TASKS[task.id] = task
    service = CheckService(settings, storage)
    try:
        report = service.check_document(
            Path(document["path"]),
            document_id=request.document_id,
            filename=document["filename"],
            ruleset=ruleset,
        )
    except DocumentValidationError as exc:
        failed = task.model_copy(
            update={"status": TaskStatus.failed, "error": str(exc), "updated_at": _now()}
        )
        CHECK_TASKS[task.id] = failed
        return failed
    except Exception as exc:
        failed = task.model_copy(
            update={"status": TaskStatus.failed, "error": str(exc), "updated_at": _now()}
        )
        CHECK_TASKS[task.id] = failed
        return failed
    REPORTS[report.id] = report
    succeeded = task.model_copy(
        update={"status": TaskStatus.succeeded, "report_id": report.id, "updated_at": _now()}
    )
    CHECK_TASKS[task.id] = succeeded
    return succeeded


@app.get("/api/check-tasks", response_model=list[CheckTask])
def list_check_tasks() -> list[CheckTask]:
    return sorted(CHECK_TASKS.values(), key=lambda task: task.created_at, reverse=True)


@app.get("/api/check-tasks/{task_id}", response_model=CheckTask)
def get_check_task(task_id: str) -> CheckTask:
    task = CHECK_TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="检查任务不存在。")
    return task


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


def _now() -> str:
    return datetime.now(UTC).isoformat()


def run() -> None:
    uvicorn.run("docchecker.api.main:app", host="127.0.0.1", port=8001, reload=True)
