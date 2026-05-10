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
        for rule in relevant_rules(rules, self.supported_categories):
            scoped_facts = [
                fact for fact in document.facts.headers_footers if _matches_scope(fact.kind, rule)
            ]
            combined_text = "\n".join(fact.text for fact in scoped_facts)
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
                document,
                rule,
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
            for field, actual_key in [
                ("fontFamilyEastAsia", "font_family_east_asia"),
                ("fontFamilyAscii", "font_family_ascii"),
                ("fontSizePt", "font_size_pt"),
            ]:
                expected = rule.expectation.get(field)
                if expected is None:
                    continue
                actual_values = _header_footer_format_values(scoped_facts, actual_key)
                if actual_values and all(value == expected for value in actual_values):
                    continue
                findings.append(
                    _finding(
                        rule,
                        field,
                        expected,
                        actual_values,
                        "页眉页脚有效格式未满足规则要求。",
                    )
                )
        return findings


def _matches_scope(kind: str, rule: FormatRule) -> bool:
    scope = rule.target.scope.lower()
    if "header_footer" in scope or "页眉页脚" in scope:
        return True
    if _scope_targets_header(scope):
        return kind.startswith("header")
    if _scope_targets_footer(scope):
        return kind.startswith("footer")
    return True


def _has_page_number(document: DocumentModel, rule: FormatRule) -> bool:
    if any(
        fact.field_type == "PAGE" and _part_matches_scope(fact.part_name, rule)
        for fact in document.facts.fields
    ):
        return True
    if any(
        "PAGE" in xml
        for name, xml in document.facts.xml_parts.items()
        if _part_matches_scope(name, rule)
    ):
        return True
    return any(
        any(char.isdigit() for char in fact.text)
        for fact in document.facts.headers_footers
        if _matches_scope(fact.kind, rule)
    )


def _part_matches_scope(part_name: str, rule: FormatRule) -> bool:
    scope = rule.target.scope.lower()
    if "header_footer" in scope or "页眉页脚" in scope:
        return "header" in part_name or "footer" in part_name
    if _scope_targets_header(scope):
        return "header" in part_name
    if _scope_targets_footer(scope):
        return "footer" in part_name
    return "header" in part_name or "footer" in part_name or part_name == "word/document.xml"


def _scope_targets_header(scope: str) -> bool:
    return any(part == "header" for part in scope.split(".")) or "页眉" in scope


def _scope_targets_footer(scope: str) -> bool:
    return any(part == "footer" for part in scope.split(".")) or "页脚" in scope


def _header_footer_format_values(facts, field: str) -> list[object]:
    values: list[object] = []
    for fact in facts:
        for paragraph in fact.paragraphs:
            if not paragraph.text.strip():
                continue
            if field in paragraph.effective_format:
                values.append(paragraph.effective_format[field])
    return values


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
