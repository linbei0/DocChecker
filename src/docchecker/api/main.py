from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import uvicorn
from fastapi import Body, FastAPI, File, HTTPException, Query, UploadFile
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
from docchecker.services.task_queue import (
    BackgroundJobEnqueueError,
    current_rq_job_is_active,
    current_rq_job_should_retry,
    start_background_job,
)
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
PUBLISH_DRAFT_RULESET_BODY = Body(default=None)


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

    name: str | None = Field(default=None, min_length=1)
    school: str | None = None
    college: str | None = None
    thesis_type: str | None = None
    version_note: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        name = value.strip()
        if not name:
            raise ValueError("模板名称不能为空。")
        return name

    @field_validator("school", "college", "thesis_type", "version_note")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)

    @model_validator(mode="after")
    def require_metadata_change(self) -> "UpdateRuleSetRequest":
        editable_fields = {"name", "school", "college", "thesis_type", "version_note"}
        if not (self.model_fields_set & editable_fields):
            raise ValueError("至少提供一个模板字段。")
        return self


class CreateDraftRuleSetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    source_type: SourceType
    manual_text: str | None = None
    requirement_document_id: str | None = None
    template_ruleset_id: str | None = None
    name: str | None = None
    school: str | None = None
    college: str | None = None
    thesis_type: str | None = None
    version_note: str | None = None

    @model_validator(mode="after")
    def validate_source_payload(self) -> "CreateDraftRuleSetRequest":
        if self.source_type == SourceType.manual and not (self.manual_text or "").strip():
            raise ValueError("手动输入规则来源必须提供 manual_text。")
        if self.source_type == SourceType.requirement_doc and not self.requirement_document_id:
            raise ValueError("规范文档规则来源必须提供 requirement_document_id。")
        if self.source_type == SourceType.template and not self.template_ruleset_id:
            raise ValueError("模板规则来源必须提供 template_ruleset_id。")
        return self

    @field_validator("name", "school", "college", "thesis_type", "version_note")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)


class UpdateDraftRuleSetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rules: list[FormatRule]
    suggested_rules: list[FormatRule] | None = None
    name: str | None = None
    parse_warnings: list[str] | None = None
    school: str | None = None
    college: str | None = None
    thesis_type: str | None = None
    version_note: str | None = None

    @field_validator("name", "school", "college", "thesis_type", "version_note")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)


class PublishDraftRuleSetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    school: str | None = None
    college: str | None = None
    thesis_type: str | None = None
    version_note: str | None = None

    @field_validator("name", "school", "college", "thesis_type", "version_note")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)


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
def list_rulesets(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    include_history: bool = Query(False),
    include_archived: bool = Query(False),
) -> list[RuleSet]:
    return state_store.list_rulesets(
        include_history=include_history,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )


@app.patch("/api/rulesets/{ruleset_id}", response_model=RuleSet)
def update_ruleset(ruleset_id: str, request: UpdateRuleSetRequest) -> RuleSet:
    ruleset = state_store.get_ruleset(ruleset_id)
    if not ruleset:
        raise HTTPException(status_code=404, detail="规则集不存在。")
    if ruleset.archived_at:
        raise HTTPException(status_code=404, detail="规则集不存在。")
    if not ruleset.is_latest:
        raise HTTPException(status_code=409, detail="历史版本不能直接更新，请更新最新版本。")
    now = _now()
    previous = ruleset.model_copy(update={"is_latest": False, "updated_at": now}, deep=True)
    updated = ruleset.model_copy(
        update={
            "id": f"ruleset_{uuid4().hex}",
            "template_id": _ruleset_template_id(ruleset),
            "name": request.name or ruleset.name,
            "school": request.school if "school" in request.model_fields_set else ruleset.school,
            "college": request.college
            if "college" in request.model_fields_set
            else ruleset.college,
            "thesis_type": request.thesis_type
            if "thesis_type" in request.model_fields_set
            else ruleset.thesis_type,
            "version": _next_patch_version(ruleset.version),
            "previous_ruleset_id": ruleset.id,
            "is_latest": True,
            "version_note": request.version_note,
            "created_at": now,
            "updated_at": now,
            "archived_at": None,
        },
        deep=True,
    )
    state_store.save_many(
        [
            ("ruleset", previous.id, previous),
            ("ruleset", updated.id, updated),
        ]
    )
    return updated


@app.get("/api/rulesets/{ruleset_id}/versions", response_model=list[RuleSet])
def list_ruleset_versions(ruleset_id: str) -> list[RuleSet]:
    versions = state_store.list_ruleset_versions(ruleset_id)
    if not versions:
        raise HTTPException(status_code=404, detail="规则集不存在。")
    return versions


@app.delete("/api/rulesets/{ruleset_id}")
def delete_ruleset(ruleset_id: str) -> dict[str, bool | str]:
    if not state_store.delete_ruleset(ruleset_id):
        raise HTTPException(status_code=404, detail="规则集不存在。")
    return {"id": ruleset_id, "deleted": True}


@app.post("/api/draft-rulesets", response_model=DraftRuleSet)
def create_draft_ruleset(
    request: CreateDraftRuleSetRequest,
) -> DraftRuleSet:
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
        school = template.school
        college = template.college
        thesis_type = template.thesis_type
        version_note = "从模板复制"
        extraction_trace = None
    else:
        text = request.manual_text or ""
        if request.source_type == SourceType.requirement_doc:
            requirement_document = state_store.get_requirement_document(
                request.requirement_document_id or ""
            )
            if not requirement_document:
                raise HTTPException(status_code=404, detail="规范文档不存在。")
            draft = DraftRuleSet(
                id=f"draft_{uuid4().hex}",
                document_id=request.document_id,
                source_type=request.source_type,
                name=request.name or "候选规则集",
                school=request.school,
                college=request.college,
                thesis_type=request.thesis_type,
                version_note=request.version_note,
                parse_warnings=["规则抽取正在后台执行，请稍后刷新。"],
                status=DraftRuleSetStatus.processing,
                created_at=now,
                updated_at=now,
            )
            state_store.save_draft_ruleset(draft)
            try:
                _start_background_job(
                    _execute_draft_ruleset_extraction,
                    draft.id,
                    requirement_document.id,
                )
            except BackgroundJobEnqueueError as exc:
                failed = draft.model_copy(
                    update={
                        "status": DraftRuleSetStatus.failed,
                        "error": str(exc),
                        "updated_at": _now(),
                    },
                    deep=True,
                )
                state_store.save_draft_ruleset(failed)
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            return draft
        try:
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
        school = request.school
        college = request.college
        thesis_type = request.thesis_type
        version_note = request.version_note

    draft = DraftRuleSet(
        id=f"draft_{uuid4().hex}",
        name=request.name or name,
        document_id=request.document_id,
        source_type=request.source_type,
        school=school,
        college=college,
        thesis_type=thesis_type,
        version_note=version_note,
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


def _execute_draft_ruleset_extraction(draft_id: str, requirement_document_id: str) -> None:
    draft = state_store.get_draft_ruleset(draft_id)
    requirement_document = state_store.get_requirement_document(requirement_document_id)
    if not draft:
        return
    if not requirement_document:
        failed = draft.model_copy(
            update={
                "parse_warnings": [],
                "status": DraftRuleSetStatus.failed,
                "error": "规范文档不存在，无法执行规则抽取。",
                "updated_at": _now(),
            },
            deep=True,
        )
        state_store.save_draft_ruleset(failed)
        return

    try:
        result = extract_rules_from_requirement_document(
            RequirementDocumentModel(
                source_filename=requirement_document.filename,
                blocks=requirement_document.blocks,
                markdown=requirement_document.extracted_text,
            ),
            source_type=SourceType.requirement_doc,
        )
        updated = draft.model_copy(
            update={
                "rules": result.rules,
                "suggested_rules": result.suggested_rules,
                "parse_warnings": result.parse_warnings,
                "extraction_summary": result.extraction_summary,
                "unsupported_requirements": result.unsupported_requirements,
                "extraction_trace": result.extraction_trace,
                "status": DraftRuleSetStatus.draft,
                "error": None,
                "updated_at": _now(),
            },
            deep=True,
        )
    except RuleExtractionConfigurationError as exc:
        updated = draft.model_copy(
            update={
                "parse_warnings": [],
                "status": DraftRuleSetStatus.failed,
                "error": str(exc),
                "updated_at": _now(),
            },
            deep=True,
        )
    except Exception as exc:
        if _save_draft_retry_or_final_failure(draft, exc):
            raise
        updated = draft.model_copy(
            update={
                "parse_warnings": [],
                "status": DraftRuleSetStatus.failed,
                "error": str(exc),
                "updated_at": _now(),
            },
            deep=True,
        )
    state_store.save_draft_ruleset(updated)


@app.get("/api/draft-rulesets/{draft_id}", response_model=DraftRuleSet)
def get_draft_ruleset(draft_id: str) -> DraftRuleSet:
    draft = state_store.get_draft_ruleset(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="候选规则集不存在。")
    return draft


@app.patch("/api/draft-rulesets/{draft_id}", response_model=DraftRuleSet)
def update_draft_ruleset(draft_id: str, request: UpdateDraftRuleSetRequest) -> DraftRuleSet:
    draft = get_draft_ruleset(draft_id)
    if draft.status == DraftRuleSetStatus.processing:
        raise HTTPException(status_code=409, detail="候选规则仍在生成中，请稍后再编辑。")
    if draft.status == DraftRuleSetStatus.failed:
        raise HTTPException(status_code=400, detail=draft.error or "候选规则生成失败。")
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
            "school": request.school if "school" in request.model_fields_set else draft.school,
            "college": request.college if "college" in request.model_fields_set else draft.college,
            "thesis_type": request.thesis_type
            if "thesis_type" in request.model_fields_set
            else draft.thesis_type,
            "version_note": request.version_note
            if "version_note" in request.model_fields_set
            else draft.version_note,
            "updated_at": _now(),
        },
        deep=True,
    )
    state_store.save_draft_ruleset(updated)
    return updated


@app.post("/api/draft-rulesets/{draft_id}/publish", response_model=RuleSet)
def publish_draft_ruleset(
    draft_id: str,
    request: PublishDraftRuleSetRequest | None = PUBLISH_DRAFT_RULESET_BODY,
) -> RuleSet:
    draft = get_draft_ruleset(draft_id)
    if draft.status == DraftRuleSetStatus.processing:
        raise HTTPException(status_code=409, detail="候选规则仍在生成中，请稍后再发布。")
    if draft.status == DraftRuleSetStatus.failed:
        raise HTTPException(status_code=400, detail=draft.error or "候选规则生成失败。")
    now = _now()
    ruleset = RuleSet(
        id=f"ruleset_{uuid4().hex}",
        template_id=f"tpl_{uuid4().hex}",
        name=request.name or draft.name if request else draft.name,
        source_type=draft.source_type,
        version=draft.version,
        locale=draft.locale,
        school=request.school
        if request and "school" in request.model_fields_set
        else draft.school,
        college=request.college
        if request and "college" in request.model_fields_set
        else draft.college,
        thesis_type=request.thesis_type
        if request and "thesis_type" in request.model_fields_set
        else draft.thesis_type,
        version_note=request.version_note
        if request and "version_note" in request.model_fields_set
        else draft.version_note,
        rules=[rule.model_copy(deep=True) for rule in draft.rules],
        created_at=now,
        updated_at=now,
    )
    published_draft = draft.model_copy(
        update={
            "status": DraftRuleSetStatus.published,
            "published_ruleset_id": ruleset.id,
            "name": ruleset.name,
            "school": ruleset.school,
            "college": ruleset.college,
            "thesis_type": ruleset.thesis_type,
            "version_note": ruleset.version_note,
            "updated_at": now,
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
def create_check_task(
    request: CreateCheckTaskRequest,
) -> CheckTask:
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
        document_filename=document.filename,
        ruleset_name=ruleset.name,
        status=TaskStatus.pending,
        created_at=_now(),
        updated_at=_now(),
    )
    state_store.save_check_task(task)
    try:
        _start_background_job(_execute_check_task, task.id)
    except BackgroundJobEnqueueError as exc:
        failed = task.model_copy(
            update={"status": TaskStatus.failed, "error": str(exc), "updated_at": _now()}
        )
        state_store.save_check_task(failed)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return task


def _start_background_job(function: Callable[..., object], *args: object) -> str | None:
    return start_background_job(settings, function, *args)


def _execute_check_task(task_id: str) -> None:
    task = state_store.get_check_task(task_id)
    if not task:
        return
    document = state_store.get_document(task.document_id)
    ruleset = state_store.get_ruleset(task.ruleset_id)
    if not document or not ruleset:
        failed = task.model_copy(
            update={
                "status": TaskStatus.failed,
                "error": "文档或规则集不存在，无法执行检查。",
                "updated_at": _now(),
            }
        )
        state_store.save_check_task(failed)
        return
    running = task.model_copy(
        update={"status": TaskStatus.running, "error": None, "updated_at": _now()}
    )
    state_store.save_check_task(running)
    service = CheckService(settings, storage)
    try:
        report = service.check_document(
            Path(document.path),
            document_id=task.document_id,
            filename=document.filename,
            ruleset=ruleset,
        )
    except DocumentValidationError as exc:
        failed = running.model_copy(
            update={"status": TaskStatus.failed, "error": str(exc), "updated_at": _now()}
        )
        state_store.save_check_task(failed)
        return
    except Exception as exc:
        if _save_check_task_retry_or_final_failure(running, exc):
            raise
        failed = running.model_copy(
            update={"status": TaskStatus.failed, "error": str(exc), "updated_at": _now()}
        )
        state_store.save_check_task(failed)
        return
    succeeded = running.model_copy(
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
        if _save_check_task_retry_or_final_failure(running, exc):
            raise
        failed = running.model_copy(
            update={"status": TaskStatus.failed, "error": str(exc), "updated_at": _now()}
        )
        state_store.save_check_task(failed)
        return


def _save_draft_retry_or_final_failure(draft: DraftRuleSet, exc: Exception) -> bool:
    if not current_rq_job_is_active():
        return False
    if current_rq_job_should_retry():
        updated = draft.model_copy(
            update={
                "status": DraftRuleSetStatus.processing,
                "error": f"上次规则抽取失败，等待 RQ 重试：{exc}",
                "updated_at": _now(),
            },
            deep=True,
        )
    else:
        updated = draft.model_copy(
            update={
                "parse_warnings": [],
                "status": DraftRuleSetStatus.failed,
                "error": str(exc),
                "updated_at": _now(),
            },
            deep=True,
        )
    state_store.save_draft_ruleset(updated)
    return True


def _save_check_task_retry_or_final_failure(task: CheckTask, exc: Exception) -> bool:
    if not current_rq_job_is_active():
        return False
    if current_rq_job_should_retry():
        updated = task.model_copy(
            update={
                "status": TaskStatus.pending,
                "error": f"上次检查失败，等待 RQ 重试：{exc}",
                "updated_at": _now(),
            }
        )
    else:
        updated = task.model_copy(
            update={"status": TaskStatus.failed, "error": str(exc), "updated_at": _now()}
        )
    state_store.save_check_task(updated)
    return True


@app.get("/api/check-tasks", response_model=list[CheckTask])
def list_check_tasks(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[CheckTask]:
    return state_store.list_check_tasks(limit=limit, offset=offset)


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


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _ruleset_template_id(ruleset: RuleSet) -> str:
    return ruleset.template_id or ruleset.id


def _next_patch_version(version: str) -> str:
    major, minor, patch = [int(part) for part in version.split(".")]
    return f"{major}.{minor}.{patch + 1}"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def run() -> None:
    uvicorn.run("docchecker.api.main:app", host="127.0.0.1", port=8001, reload=True)
