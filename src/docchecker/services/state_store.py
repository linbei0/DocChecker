import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, TypeVar

from pydantic import BaseModel

from docchecker.domain.document import UploadedDocumentRecord
from docchecker.domain.findings import CheckReport
from docchecker.domain.requirements import RequirementDocument
from docchecker.domain.rules import DraftRuleSet, RuleSet
from docchecker.domain.tasks import CheckTask

RecordKind = Literal[
    "document",
    "requirement_document",
    "ruleset",
    "draft_ruleset",
    "check_task",
    "report",
]

VALID_KINDS: set[str] = {
    "document",
    "requirement_document",
    "ruleset",
    "draft_ruleset",
    "check_task",
    "report",
}

ModelT = TypeVar("ModelT", bound=BaseModel)


class SqliteStateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS state_records (
                    kind TEXT NOT NULL,
                    id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (kind, id)
                )
                """
            )

    def save_record(self, kind: RecordKind, record_id: str, payload: BaseModel) -> None:
        self._ensure_kind(kind)
        with self._connect() as connection:
            self._upsert(connection, kind, record_id, payload)

    def save_many(self, records: list[tuple[RecordKind, str, BaseModel]]) -> None:
        with self._connect() as connection:
            # 关联状态必须同事务落库，避免任务成功但报告缺失等半写入状态。
            for kind, record_id, payload in records:
                self._ensure_kind(kind)
                self._upsert(connection, kind, record_id, payload)

    def get_record(
        self,
        kind: RecordKind,
        record_id: str,
        model_type: type[ModelT],
    ) -> ModelT | None:
        self._ensure_kind(kind)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM state_records WHERE kind = ? AND id = ?",
                (kind, record_id),
            ).fetchone()
        if row is None:
            return None
        return model_type.model_validate_json(row[0])

    def list_records(
        self,
        kind: RecordKind,
        model_type: type[ModelT],
        *,
        newest_first: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ModelT]:
        self._ensure_kind(kind)
        if limit < 1:
            raise ValueError("limit 必须大于 0。")
        if offset < 0:
            raise ValueError("offset 不能小于 0。")
        order = "DESC" if newest_first else "ASC"
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM state_records "
                f"WHERE kind = ? ORDER BY created_at {order}, id {order} LIMIT ? OFFSET ?",
                (kind, limit, offset),
            ).fetchall()
        return [model_type.model_validate_json(row[0]) for row in rows]

    def delete_record(self, kind: RecordKind, record_id: str) -> bool:
        self._ensure_kind(kind)
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM state_records WHERE kind = ? AND id = ?",
                (kind, record_id),
            )
        return cursor.rowcount > 0

    def save_document(self, document: UploadedDocumentRecord) -> None:
        self.save_record("document", document.id, document)

    def get_document(self, document_id: str) -> UploadedDocumentRecord | None:
        return self.get_record("document", document_id, UploadedDocumentRecord)

    def save_requirement_document(self, document: RequirementDocument) -> None:
        self.save_record("requirement_document", document.id, document)

    def get_requirement_document(self, document_id: str) -> RequirementDocument | None:
        return self.get_record("requirement_document", document_id, RequirementDocument)

    def save_ruleset(self, ruleset: RuleSet) -> None:
        self.save_record("ruleset", ruleset.id, ruleset)

    def get_ruleset(self, ruleset_id: str) -> RuleSet | None:
        return self.get_record("ruleset", ruleset_id, RuleSet)

    def list_rulesets(
        self,
        *,
        include_history: bool = False,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RuleSet]:
        rulesets = self.list_records(
            "ruleset",
            RuleSet,
            newest_first=True,
            limit=10000,
            offset=0,
        )
        filtered = [
            ruleset
            for ruleset in rulesets
            if (include_history or ruleset.is_latest)
            and (include_archived or ruleset.archived_at is None)
        ]
        return filtered[offset : offset + limit]

    def list_ruleset_versions(
        self,
        ruleset_id: str,
        *,
        include_archived: bool = False,
    ) -> list[RuleSet]:
        current = self.get_ruleset(ruleset_id)
        if current is None:
            return []
        template_id = current.template_id or current.id
        versions = [
            ruleset
            for ruleset in self.list_rulesets(
                include_history=True,
                include_archived=include_archived,
                limit=10000,
            )
            if (ruleset.template_id or ruleset.id) == template_id
        ]
        return sorted(versions, key=lambda item: item.created_at, reverse=True)

    def delete_ruleset(self, ruleset_id: str) -> bool:
        ruleset = self.get_ruleset(ruleset_id)
        if ruleset is None:
            return False
        if ruleset.archived_at is not None:
            return False
        archived_at = _now()
        versions = self.list_ruleset_versions(ruleset_id, include_archived=True)
        self.save_many(
            [
                (
                    "ruleset",
                    version.id,
                    version.model_copy(
                        update={"archived_at": archived_at, "updated_at": archived_at}
                    ),
                )
                for version in versions
            ]
        )
        return True

    def save_draft_ruleset(self, draft: DraftRuleSet) -> None:
        self.save_record("draft_ruleset", draft.id, draft)

    def get_draft_ruleset(self, draft_id: str) -> DraftRuleSet | None:
        return self.get_record("draft_ruleset", draft_id, DraftRuleSet)

    def save_check_task(self, task: CheckTask) -> None:
        self.save_record("check_task", task.id, task)

    def get_check_task(self, task_id: str) -> CheckTask | None:
        return self.get_record("check_task", task_id, CheckTask)

    def list_check_tasks(self, *, limit: int = 50, offset: int = 0) -> list[CheckTask]:
        return self.list_records(
            "check_task",
            CheckTask,
            newest_first=True,
            limit=limit,
            offset=offset,
        )

    def delete_check_task(self, task_id: str) -> bool:
        return self.delete_record("check_task", task_id)

    def save_report(self, report: CheckReport) -> None:
        self.save_record("report", report.id, report)

    def get_report(self, report_id: str) -> CheckReport | None:
        return self.get_record("report", report_id, CheckReport)

    def delete_report(self, report_id: str) -> bool:
        return self.delete_record("report", report_id)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, check_same_thread=False)

    def _upsert(
        self,
        connection: sqlite3.Connection,
        kind: RecordKind,
        record_id: str,
        payload: BaseModel,
    ) -> None:
        now = _now()
        created_at = (
            _model_str_attr(payload, "created_at")
            or _model_str_attr(payload, "generated_at")
            or now
        )
        updated_at = _model_str_attr(payload, "updated_at") or created_at
        connection.execute(
            """
            INSERT INTO state_records (kind, id, payload, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(kind, id) DO UPDATE SET
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                kind,
                record_id,
                payload.model_dump_json(exclude_computed_fields=True),
                created_at,
                updated_at,
            ),
        )

    def _ensure_kind(self, kind: str) -> None:
        if kind not in VALID_KINDS:
            raise ValueError(f"Unsupported state record kind: {kind}")


def _model_str_attr(payload: BaseModel, name: str) -> str | None:
    value = getattr(payload, name, None)
    return value if isinstance(value, str) and value else None


def _now() -> str:
    return datetime.now(UTC).isoformat()
