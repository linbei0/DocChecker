import re

from docchecker.domain.document import DocumentModel, ParagraphNode
from docchecker.domain.rules import FormatRule


class ParagraphMatchIndex:
    """缓存常用段落分组，避免每条规则重复扫描整篇文档。"""

    def __init__(self, document: DocumentModel) -> None:
        self.document = document
        self.paragraphs = [paragraph for paragraph in document.paragraphs if paragraph.text.strip()]
        self.non_heading_paragraphs = [
            paragraph
            for paragraph in self.paragraphs
            if not (paragraph.style_name or "").lower().startswith("heading")
        ]
        self.table_cell_paragraphs = [
            paragraph for paragraph in self.paragraphs if paragraph.table_index is not None
        ]
        self.toc_indexes = {
            paragraph.index for paragraph in self.paragraphs if self._is_toc_paragraph(paragraph)
        }
        self.body_paragraphs = [
            paragraph for paragraph in self.paragraphs if self._is_body_paragraph(paragraph)
        ]

    def match_font_rule(self, rule: FormatRule) -> list[ParagraphNode]:
        selector = rule.target.selector
        if _is_ambiguous_heading_candidate(rule):
            return []
        if rule.target.scope.startswith("heading"):
            return [
                paragraph
                for paragraph in self.paragraphs
                if paragraph.index not in self.toc_indexes
                and _matches_heading_level(paragraph, rule.target.scope, selector)
            ]
        if _is_table_cell_scope(rule.target.scope):
            return _selector_matches(self.table_cell_paragraphs, selector)
        if rule.target.scope.startswith("body"):
            return self.body_paragraphs
        if selector:
            return _selector_matches(self.paragraphs, selector)
        return self.paragraphs

    def match_paragraph_rule(self, rule: FormatRule) -> list[ParagraphNode]:
        selector = rule.target.selector
        if _is_ambiguous_heading_candidate(rule):
            return []
        if rule.target.scope.startswith("heading"):
            return [
                paragraph
                for paragraph in self.paragraphs
                if paragraph.index not in self.toc_indexes
                and _matches_heading_level(paragraph, rule.target.scope, selector)
            ]
        if _is_table_cell_scope(rule.target.scope):
            return _selector_matches(self.table_cell_paragraphs, selector)
        if rule.target.scope.startswith("body"):
            return self.body_paragraphs
        if _is_document_body_selector(rule.target.scope, selector):
            return _selector_matches(self.body_paragraphs, selector)
        if selector:
            return _selector_matches(self.non_heading_paragraphs, selector)
        return self.non_heading_paragraphs

    def _is_toc_paragraph(self, paragraph: ParagraphNode) -> bool:
        return any(
            section.role == "toc"
            and section.start_paragraph_index
            <= paragraph.index
            <= (section.end_paragraph_index or paragraph.index)
            for section in self.document.logical_sections
        )

    def _is_body_paragraph(self, paragraph: ParagraphNode) -> bool:
        in_body_section = any(
            section.role == "body"
            and section.start_paragraph_index
            <= paragraph.index
            <= (section.end_paragraph_index or paragraph.index)
            for section in self.document.logical_sections
        )
        if not in_body_section:
            return False
        if paragraph.index in self.toc_indexes:
            return False
        if paragraph.table_index is not None:
            return False
        if _matches_heading_level(paragraph, "heading", None):
            return False
        return not _is_caption_paragraph(paragraph)


def _selector_matches(
    paragraphs: list[ParagraphNode],
    selector: str | None,
) -> list[ParagraphNode]:
    if not selector:
        return paragraphs
    return [
        paragraph
        for paragraph in paragraphs
        if paragraph.style_name == selector or selector in paragraph.text
    ]


def _is_table_cell_scope(scope: str) -> bool:
    normalized = scope.lower().replace("-", "_")
    return normalized.startswith(("table_cell", "table.cell", "table.paragraph"))


def _is_document_body_selector(scope: str, selector: str | None) -> bool:
    return scope.lower() in {"document", "paragraph"} and selector in {
        "正文",
        "正文段落",
        "body",
        "body.paragraph",
    }


def _is_ambiguous_heading_candidate(rule: FormatRule) -> bool:
    if rule.target.scope.lower() not in {"heading", "heading.paragraph"}:
        return False
    selector = rule.target.selector or ""
    if selector not in {"一级标题", "二级标题", "三级标题"}:
        return False
    return selector not in rule.source.excerpt


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
    if match := re.match(r"^\s*(\d+(?:\.\d+){0,5})\s+(.+?)\s*$", text):
        title = match.group(2).strip()
        if title and not title.isdigit():
            return match.group(1).count(".") + 1
    return None


def _is_caption_paragraph(paragraph: ParagraphNode) -> bool:
    text = paragraph.text.strip()
    return bool(re.match(r"^(续)?(图|表)\s*\d+(?:[.-]\d+)*\s+.+", text))
