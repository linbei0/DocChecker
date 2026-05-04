from docchecker.checkers.base import Checker
from docchecker.checkers.font import FontChecker
from docchecker.checkers.header_footer import HeaderFooterChecker
from docchecker.checkers.ooxml import OoxmlRuleChecker
from docchecker.checkers.page_setup import PageSetupChecker
from docchecker.checkers.paragraph import ParagraphChecker
from docchecker.checkers.property import PropertyChecker
from docchecker.checkers.semantic import (
    AbstractChecker,
    CaptionChecker,
    ReferenceChecker,
    StructureChecker,
    TocChecker,
)
from docchecker.domain.document import DocumentModel
from docchecker.domain.findings import CheckFinding, FindingLocation
from docchecker.domain.rules import FormatRule


class CheckExecutionError(RuntimeError):
    """检查器执行失败。"""


class CheckEngine:
    def __init__(self, checkers: list[Checker] | None = None) -> None:
        self.checkers = checkers or [
            PageSetupChecker(),
            FontChecker(),
            ParagraphChecker(),
            HeaderFooterChecker(),
            StructureChecker(),
            TocChecker(),
            CaptionChecker(),
            ReferenceChecker(),
            AbstractChecker(),
            PropertyChecker(),
            OoxmlRuleChecker(),
        ]

    def run(self, document: DocumentModel, rules: list[FormatRule]) -> list[CheckFinding]:
        findings: list[CheckFinding] = []
        for checker in self.checkers:
            try:
                findings.extend(checker.check(document, rules))
            except Exception as exc:
                findings.append(
                    CheckFinding(
                        id=f"{checker.checker_id}:checker_failed",
                        rule_id="__checker_execution__",
                        checker_id=checker.checker_id,
                        category=None,
                        severity="blocker",
                        location=FindingLocation(area="checker"),
                        expected={"status": "checker_succeeded"},
                        actual={"error": str(exc)},
                        evidence=f"检查器 {checker.checker_id} 执行失败。",
                        suggestion="请查看服务端错误日志并修复检查器实现或规则输入。",
                    )
                )
        return findings
