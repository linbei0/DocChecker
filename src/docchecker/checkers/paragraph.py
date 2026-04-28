from docchecker.checkers.base import relevant_rules
from docchecker.checkers.finding_context import (
    paragraph_context,
    paragraph_evidence,
    paragraph_excerpt,
    paragraph_location,
)
from docchecker.domain.document import DocumentModel, ParagraphNode
from docchecker.domain.enums import Certainty, RuleCategory
from docchecker.domain.findings import CheckFinding
from docchecker.domain.rules import FormatRule


class ParagraphChecker:
    checker_id = "paragraph_checker"
    supported_categories = {RuleCategory.paragraph}

    def check(self, document: DocumentModel, rules: list[FormatRule]) -> list[CheckFinding]:
        findings: list[CheckFinding] = []
        for rule in relevant_rules(rules, self.supported_categories):
            for paragraph in _matching_paragraphs(document, rule):
                for field, expected in rule.expectation.items():
                    actual = getattr(paragraph, _field_name(field), None)
                    if actual is None:
                        findings.append(
                            self._finding(
                                document,
                                rule,
                                paragraph,
                                field,
                                expected,
                                actual,
                                Certainty.unknown,
                            )
                        )
                    elif not _matches(actual, expected, rule.tolerance.get(field, 0)):
                        findings.append(
                            self._finding(document, rule, paragraph, field, expected, actual)
                        )
        return findings

    def _finding(
        self,
        document: DocumentModel,
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
            location=paragraph_location(paragraph),
            expected={field: expected},
            actual={field: actual},
            excerpt=paragraph_excerpt(paragraph.text),
            context=paragraph_context(
                document, paragraph, field, expected=expected, actual=actual
            ),
            evidence=paragraph_evidence(
                paragraph,
                field,
                expected=expected,
                actual=actual,
                checker_label="段落字段",
            ),
            suggestion="请调整该段缩进、行距、段前段后或对齐方式。",
            certainty=certainty,
        )


def _matching_paragraphs(document: DocumentModel, rule: FormatRule) -> list[ParagraphNode]:
    selector = rule.target.selector
    if selector:
        return [
            p
            for p in document.paragraphs
            if p.text.strip() and (p.style_name == selector or selector in p.text)
        ]
    return [p for p in document.paragraphs if p.text.strip()]


def _field_name(field: str) -> str:
    return {
        "firstLineIndentCm": "first_line_indent_cm",
        "lineSpacing": "line_spacing",
        "spaceBeforePt": "space_before_pt",
        "spaceAfterPt": "space_after_pt",
        "fontFamilyEastAsia": "font_family",
        "fontSizePt": "font_size_pt",
    }.get(field, field)


def _matches(actual, expected, tolerance) -> bool:
    if isinstance(actual, int | float) and isinstance(expected, int | float):
        return abs(actual - expected) <= tolerance
    return actual == expected
