from docchecker.checkers.base import relevant_rules
from docchecker.domain.document import DocumentModel, ParagraphNode
from docchecker.domain.enums import Certainty, RuleCategory
from docchecker.domain.findings import CheckFinding, FindingLocation
from docchecker.domain.rules import FormatRule


class FontChecker:
    checker_id = "font_checker"
    supported_categories = {RuleCategory.font}

    def check(self, document: DocumentModel, rules: list[FormatRule]) -> list[CheckFinding]:
        findings: list[CheckFinding] = []
        for rule in relevant_rules(rules, self.supported_categories):
            for paragraph in _matching_paragraphs(document, rule):
                for field, expected in rule.expectation.items():
                    actual = getattr(paragraph, _field_name(field), None)
                    if actual is None:
                        findings.append(
                            self._finding(
                                rule, paragraph, field, expected, actual, Certainty.unknown
                            )
                        )
                    elif not _matches(actual, expected, rule.tolerance.get(field, 0)):
                        findings.append(self._finding(rule, paragraph, field, expected, actual))
        return findings

    def _finding(
        self,
        rule: FormatRule,
        paragraph: ParagraphNode,
        field: str,
        expected,
        actual,
        certainty: Certainty = Certainty.certain,
    ) -> CheckFinding:
        return CheckFinding(
            id=f"{rule.id}:paragraph-{paragraph.index}:{field}",
            rule_id=rule.id,
            checker_id=self.checker_id,
            category=rule.category,
            severity=rule.severity,
            location=FindingLocation(paragraph_index=paragraph.index),
            expected={field: expected},
            actual={field: actual},
            evidence=f"第 {paragraph.index + 1} 段字体字段 {field} 与规则不一致。",
            suggestion="请调整该段字体、字号或加粗设置，或清除直接格式后应用目标样式。",
            certainty=certainty,
        )


def _matching_paragraphs(document: DocumentModel, rule: FormatRule) -> list[ParagraphNode]:
    selector = rule.target.selector
    if selector:
        return [p for p in document.paragraphs if p.style_name == selector and p.text.strip()]
    return [p for p in document.paragraphs if p.text.strip()]


def _field_name(field: str) -> str:
    return {
        "fontFamilyEastAsia": "font_family",
        "fontSizePt": "font_size_pt",
    }.get(field, field)


def _matches(actual, expected, tolerance) -> bool:
    if isinstance(actual, int | float) and isinstance(expected, int | float):
        return abs(actual - expected) <= tolerance
    return actual == expected
