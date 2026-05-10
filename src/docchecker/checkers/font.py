import re

from docchecker.checkers.base import relevant_rules
from docchecker.checkers.finding_context import (
    paragraph_context,
    paragraph_evidence,
    paragraph_excerpt,
    paragraph_location,
)
from docchecker.checkers.paragraph_index import ParagraphMatchIndex
from docchecker.domain.document import DocumentModel, ParagraphNode
from docchecker.domain.enums import Certainty, RuleCategory
from docchecker.domain.findings import CheckFinding
from docchecker.domain.rules import FormatRule


class FontChecker:
    checker_id = "font_checker"
    supported_categories = {RuleCategory.font, RuleCategory.heading}

    def check(self, document: DocumentModel, rules: list[FormatRule]) -> list[CheckFinding]:
        findings: list[CheckFinding] = []
        paragraph_index = ParagraphMatchIndex(document)
        for rule in relevant_rules(rules, self.supported_categories):
            for paragraph in paragraph_index.match_font_rule(rule):
                for field, expected in rule.expectation.items():
                    actual = _actual_value(paragraph, field, expected, rule.target.scope)
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
                checker_label="字体字段",
            ),
            suggestion="请调整该段字体、字号或加粗设置，或清除直接格式后应用目标样式。",
            certainty=certainty,
            status=_finding_status(actual),
        )


def _matching_paragraphs(document: DocumentModel, rule: FormatRule) -> list[ParagraphNode]:
    selector = rule.target.selector
    paragraphs = [p for p in document.paragraphs if p.text.strip()]
    if rule.target.scope.startswith("heading"):
        return [
            p
            for p in paragraphs
            if not _is_toc_paragraph(document, p)
            and _matches_heading_level(p, rule.target.scope, selector)
        ]
    if rule.target.scope.startswith("body"):
        return [p for p in paragraphs if _is_body_paragraph(document, p)]
    if selector:
        return [
            p
            for p in paragraphs
            if p.style_name == selector or selector in p.text
        ]
    return paragraphs


def _matches_heading_level(
    paragraph: ParagraphNode,
    scope: str,
    selector: str | None,
) -> bool:
    style_name = paragraph.style_name or ""
    if selector and style_name == selector:
        return True
    expected_level = _heading_level(scope, selector)
    if expected_level is None:
        return style_name.lower().startswith("heading")
    style_level = _style_heading_level(style_name)
    if style_level is not None:
        return style_level == expected_level
    text_level = _numbered_heading_level(paragraph.text)
    return text_level == expected_level


def _heading_level(scope: str, selector: str | None) -> int | None:
    for value in [scope, selector or ""]:
        if match := re.search(r"(?:heading[ .]?|heading\.)([1-6])", value, re.I):
            return int(match.group(1))
    return None


def _style_heading_level(style_name: str) -> int | None:
    if match := re.search(r"heading\s*([1-6])", style_name, re.I):
        return int(match.group(1))
    return None


def _numbered_heading_level(text: str) -> int | None:
    if re.match(r"^\s*\d+(?:\.\d+){0,5}\s+.+\s+\d+\s*$", text):
        return None
    if match := re.match(r"^\s*\d+(?:\.\d+){0,5}(?=\s|\t|$)", text):
        return match.group(0).count(".") + 1
    return None


def _is_toc_paragraph(document: DocumentModel, paragraph: ParagraphNode) -> bool:
    return any(
        section.role == "toc"
        and section.start_paragraph_index
        <= paragraph.index
        <= (section.end_paragraph_index or paragraph.index)
        for section in document.logical_sections
    )


def _is_body_paragraph(document: DocumentModel, paragraph: ParagraphNode) -> bool:
    in_body_section = any(
        section.role == "body"
        and section.start_paragraph_index
        <= paragraph.index
        <= (section.end_paragraph_index or paragraph.index)
        for section in document.logical_sections
    )
    if not in_body_section:
        return False
    if _is_toc_paragraph(document, paragraph):
        return False
    if _matches_heading_level(paragraph, "heading", None):
        return False
    return not _is_caption_paragraph(paragraph)


def _is_caption_paragraph(paragraph: ParagraphNode) -> bool:
    text = paragraph.text.strip()
    return bool(re.match(r"^(续)?(图|表)\s*\d+(?:[.-]\d+)*\s+.+", text))


def _field_name(field: str) -> str:
    return {
        "fontFamilyEastAsia": "font_family",
        "fontFamilyAscii": "font_family_ascii",
        "fontSizePt": "font_size_pt",
        "spaceBeforePt": "space_before_pt",
        "spaceAfterPt": "space_after_pt",
    }.get(field, field)


def _actual_value(paragraph: ParagraphNode, field: str, expected, scope: str = ""):
    if field == "fontFamilyAscii":
        return (
            paragraph.font_family_ascii
            or _mixed_font_value(paragraph.raw.get("font_family_ascii_values"))
            or paragraph.font_family
        )
    if field == "fontFamilyEastAsia":
        if scope.startswith("keywords"):
            return _keyword_font_value(paragraph, expected)
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
    if field == "bold":
        return paragraph.bold if paragraph.bold is not None else False
    return getattr(paragraph, _field_name(field), None)


def _keyword_font_value(paragraph: ParagraphNode, expected):
    content_runs = _keyword_content_runs(paragraph)
    if isinstance(expected, str) and _is_latin_font(expected):
        return _single_or_mixed(
            run.font_family_ascii
            for run in content_runs
            if run.script in {"ascii", "mixed"} and run.font_family_ascii
        )
    east_asia_fonts = [
        run.font_family_east_asia
        for run in content_runs
        if run.script in {"east_asia", "mixed"}
        and run.font_family_east_asia
        and not _is_latin_font(run.font_family_east_asia)
    ]
    if not east_asia_fonts and _has_east_asia_text(content_runs):
        return expected
    return _single_or_mixed(east_asia_fonts)


def _keyword_content_runs(paragraph: ParagraphNode):
    runs = list(paragraph.runs)
    if runs and runs[0].text.strip().startswith(("关键词", "关键字")):
        first = runs[0].model_copy()
        _, separator, tail = first.text.partition("：")
        if not separator:
            _, separator, tail = first.text.partition(":")
        if separator:
            first.text = tail
            runs = ([first] if tail else []) + runs[1:]
        else:
            runs = runs[1:]
    return runs


def _single_or_mixed(values) -> str | None:
    names: list[str] = []
    for value in values:
        if value and value not in names:
            names.append(str(value))
    if len(names) <= 1:
        return names[0] if names else None
    return "混合：" + "、".join(names)


def _has_east_asia_text(runs) -> bool:
    return any(run.script in {"east_asia", "mixed"} for run in runs)


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
