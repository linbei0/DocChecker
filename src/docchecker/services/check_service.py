from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from docchecker.checkers.engine import CheckEngine
from docchecker.core.config import Settings
from docchecker.domain.findings import CheckReport
from docchecker.domain.rules import RuleSet
from docchecker.parsing.docx_parser import parse_docx
from docchecker.reports.markdown import render_markdown_report
from docchecker.services.docx_validator import validate_docx_path
from docchecker.services.file_storage import LocalFileStorage


class CheckService:
    def __init__(self, settings: Settings, storage: LocalFileStorage) -> None:
        self.settings = settings
        self.storage = storage
        self.engine = CheckEngine()

    def check_document(
        self,
        path: Path,
        *,
        document_id: str,
        filename: str,
        ruleset: RuleSet,
    ) -> CheckReport:
        validate_docx_path(path, max_size_bytes=self.settings.max_document_size_bytes)
        document = parse_docx(path, document_id=document_id, source_filename=filename)
        findings = self.engine.run(document, ruleset.rules)
        report = CheckReport(
            id=f"report_{uuid4().hex}",
            document_id=document_id,
            ruleset_id=ruleset.id,
            checker_version=self.settings.checker_version,
            generated_at=datetime.now(UTC).isoformat(),
            findings=findings,
            parse_warnings=[warning.message for warning in document.parse_warnings],
        )
        report_content = render_markdown_report(report)
        self.storage.report_path(report.id).write_text(report_content, encoding="utf-8")
        return report
