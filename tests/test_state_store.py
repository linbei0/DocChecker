from pathlib import Path

from docchecker.domain.document import UploadedDocumentRecord
from docchecker.domain.enums import SourceType, TaskStatus
from docchecker.domain.findings import CheckReport
from docchecker.domain.requirements import RequirementDocument
from docchecker.domain.rules import DraftRuleSet, RuleSet
from docchecker.domain.tasks import CheckTask
from docchecker.services.state_store import SqliteStateStore


def test_state_store_persists_records_after_reopen(tmp_path: Path) -> None:
    database_path = tmp_path / "state.sqlite3"
    store = SqliteStateStore(database_path)
    store.initialize()

    document = UploadedDocumentRecord(
        id="doc_1",
        filename="paper.docx",
        path="storage/documents/doc_1.docx",
        original_path="storage/documents/doc_1.docx",
        original_format="docx",
        normalized_format="docx",
        size_bytes=128,
    )
    requirement_document = RequirementDocument(
        id="req_1",
        filename="rules.docx",
        path="storage/documents/req_1.docx",
        size_bytes=256,
        extracted_text="正文宋体小四",
        original_format="docx",
        normalized_format="docx",
        created_at="2026-05-03T00:00:00+00:00",
    )
    ruleset = RuleSet(
        id="ruleset_1",
        name="默认规则",
        source_type=SourceType.manual,
        version="1.0.0",
        rules=[],
        created_at="2026-05-03T00:00:01+00:00",
    )
    draft = DraftRuleSet(
        id="draft_1",
        name="候选规则集",
        document_id=document.id,
        source_type=SourceType.manual,
        rules=[],
        created_at="2026-05-03T00:00:02+00:00",
        updated_at="2026-05-03T00:00:02+00:00",
    )
    task = CheckTask(
        id="task_1",
        document_id=document.id,
        ruleset_id=ruleset.id,
        status=TaskStatus.succeeded,
        report_id="report_1",
        created_at="2026-05-03T00:00:03+00:00",
        updated_at="2026-05-03T00:00:04+00:00",
    )
    report = CheckReport(
        id="report_1",
        document_id=document.id,
        ruleset_id=ruleset.id,
        checker_version="0.1.0",
        generated_at="2026-05-03T00:00:04+00:00",
        findings=[],
    )

    store.save_document(document)
    store.save_requirement_document(requirement_document)
    store.save_draft_ruleset(draft)
    store.save_many(
        [
            ("ruleset", ruleset.id, ruleset),
            ("check_task", task.id, task),
            ("report", report.id, report),
        ]
    )

    reopened = SqliteStateStore(database_path)
    reopened.initialize()

    assert reopened.get_document(document.id) == document
    assert reopened.get_requirement_document(requirement_document.id) == requirement_document
    assert reopened.get_ruleset(ruleset.id) == ruleset
    assert reopened.get_draft_ruleset(draft.id) == draft
    assert reopened.get_check_task(task.id) == task
    assert reopened.get_report(report.id) == report

    assert reopened.delete_ruleset(ruleset.id) is True
    assert reopened.delete_check_task(task.id) is True
    assert reopened.delete_report(report.id) is True
    assert reopened.delete_ruleset("missing_ruleset") is False
    assert reopened.get_ruleset(ruleset.id) is None
    assert reopened.get_check_task(task.id) is None
    assert reopened.get_report(report.id) is None


def test_state_store_lists_records_with_limit_and_offset(tmp_path: Path) -> None:
    store = SqliteStateStore(tmp_path / "state.sqlite3")
    store.initialize()
    rulesets = [
        RuleSet(
            id=f"ruleset_{index}",
            name=f"规则集 {index}",
            source_type=SourceType.manual,
            version="1.0.0",
            rules=[],
            created_at=f"2026-05-03T00:00:0{index}+00:00",
        )
        for index in range(3)
    ]
    tasks = [
        CheckTask(
            id=f"task_{index}",
            document_id="doc_1",
            ruleset_id="ruleset_1",
            status=TaskStatus.succeeded,
            created_at=f"2026-05-03T00:00:0{index}+00:00",
            updated_at=f"2026-05-03T00:00:0{index}+00:00",
        )
        for index in range(3)
    ]
    store.save_many(
        [("ruleset", ruleset.id, ruleset) for ruleset in rulesets]
        + [("check_task", task.id, task) for task in tasks]
    )

    assert [item.id for item in store.list_rulesets(limit=2, offset=1)] == [
        "ruleset_1",
        "ruleset_2",
    ]
    assert [item.id for item in store.list_check_tasks(limit=2)] == ["task_2", "task_1"]
