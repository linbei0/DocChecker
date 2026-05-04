from docchecker.checkers.base import relevant_rules
from docchecker.domain.document import DocumentModel
from docchecker.domain.enums import RuleCategory
from docchecker.domain.findings import CheckFinding, FindingLocation
from docchecker.domain.rules import FormatRule


class HeaderFooterChecker:
    checker_id = "header_footer"
    supported_categories = {RuleCategory.header_footer}

    def check(self, document: DocumentModel, rules: list[FormatRule]) -> list[CheckFinding]:
        findings: list[CheckFinding] = []
        combined_text = "\n".join(fact.text for fact in document.facts.headers_footers)
        for rule in relevant_rules(rules, self.supported_categories):
            expected_text = rule.expectation.get("textContains")
            if isinstance(expected_text, str) and expected_text not in combined_text:
                findings.append(
                    _finding(
                        rule,
                        "textContains",
                        expected_text,
                        combined_text,
                        "页眉页脚未包含规则要求的文本。",
                    )
                )
            if rule.expectation.get("requiresPageNumber") is True and not _has_page_number(
                document
            ):
                findings.append(
                    _finding(
                        rule,
                        "requiresPageNumber",
                        True,
                        False,
                        "页眉页脚未发现页码域或页码文本。",
                    )
                )
        return findings


def _has_page_number(document: DocumentModel) -> bool:
    if any(fact.field_type == "PAGE" for fact in document.facts.fields):
        return True
    if any("PAGE" in xml for name, xml in document.facts.xml_parts.items() if "footer" in name):
        return True
    return any(any(char.isdigit() for char in fact.text) for fact in document.facts.headers_footers)


def _finding(
    rule: FormatRule,
    field: str,
    expected,
    actual,
    evidence: str,
) -> CheckFinding:
    return CheckFinding(
        id=f"header_footer:{rule.id}:{field}",
        rule_id=rule.id,
        checker_id="header_footer",
        category=rule.category,
        severity=rule.severity,
        location=FindingLocation(area="header_footer"),
        expected={field: expected},
        actual={field: actual},
        evidence=evidence,
        suggestion="请检查页眉页脚内容、页码域和节继承设置。",
    )
