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
                    actual = _actual_value(paragraph, field, expected)
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
            status=_finding_status(actual),
        )


def _matching_paragraphs(document: DocumentModel, rule: FormatRule) -> list[ParagraphNode]:
    selector = rule.target.selector
    paragraphs = [p for p in document.paragraphs if p.text.strip()]
    if rule.target.scope.startswith("heading"):
        heading_paragraphs = [
            p
            for p in paragraphs
            if (p.style_name or "").lower().startswith("heading")
        ]
        if not selector:
            return heading_paragraphs
        selected = [
            p
            for p in heading_paragraphs
            if p.style_name == selector or p.text.strip() == selector
        ]
        return selected or heading_paragraphs
    paragraphs = [
        p for p in paragraphs if not (p.style_name or "").lower().startswith("heading")
    ]
    if selector:
        return [
            p
            for p in paragraphs
            if p.style_name == selector or selector in p.text
        ]
    return paragraphs


def _field_name(field: str) -> str:
    return {
        "firstLineIndentCm": "first_line_indent_cm",
        "lineSpacing": "line_spacing",
        "spaceBeforePt": "space_before_pt",
        "spaceAfterPt": "space_after_pt",
        "fontFamilyEastAsia": "font_family",
        "fontSizePt": "font_size_pt",
    }.get(field, field)


def _actual_value(paragraph: ParagraphNode, field: str, expected):
    if field == "fontFamilyEastAsia":
        if isinstance(expected, str) and _is_latin_font(expected):
            return (
                paragraph.font_family_ascii
                or _mixed_font_value(paragraph.raw.get("font_family_ascii_values"))
                or paragraph.font_family
            )
        return (
            paragraph.font_family_east_asia
            or _mixed_font_value(paragraph.raw.get("font_family_east_asia_values"))
            or paragraph.font_family
        )
    return getattr(paragraph, _field_name(field), None)


def _mixed_font_value(values) -> str | None:
    if not isinstance(values, list):
        return None
    names = [str(value) for value in values if value]
    if len(names) <= 1:
        return names[0] if names else None
    return "混合：" + "、".join(names)


def _finding_status(actual) -> str:
    if actual is None:
        return "missing_actual"
    if isinstance(actual, str) and actual.startswith("混合："):
        return "mixed_value"
    return "mismatch"


def _is_latin_font(value: str) -> bool:
    return value.lower() in {"times new roman", "arial", "calibri", "cambria"}


def _matches(actual, expected, tolerance) -> bool:
    if isinstance(actual, int | float) and isinstance(expected, int | float):
        return abs(actual - expected) <= tolerance
    return actual == expected
