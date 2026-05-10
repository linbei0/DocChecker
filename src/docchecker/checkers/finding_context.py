from typing import Any

from docchecker.domain.document import DocumentModel, ParagraphNode
from docchecker.domain.findings import FindingLocation

MAX_EXCERPT_LENGTH = 96


FIELD_LABELS = {
    "fontFamilyEastAsia": "中文字体",
    "fontFamilyAscii": "英文字体",
    "fontSizePt": "字号",
    "bold": "加粗",
    "firstLineIndentCm": "首行缩进",
    "lineSpacing": "行距",
    "spaceBeforePt": "段前间距",
    "spaceAfterPt": "段后间距",
    "alignment": "对齐方式",
}


def paragraph_excerpt(text: str, *, max_length: int = MAX_EXCERPT_LENGTH) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[: max_length - 1]}…"


def paragraph_location(paragraph: ParagraphNode) -> FindingLocation:
    paragraph_number = paragraph.index + 1
    section_name = paragraph.raw.get("section_name")
    if not isinstance(section_name, str) or not section_name.strip():
        section_name = None
    display_parts = [section_name] if section_name else []
    if paragraph.table_index is not None:
        table_number = paragraph.table_index + 1
        row_number = (paragraph.row_index or 0) + 1
        column_number = (paragraph.column_index or 0) + 1
        display_parts.append(f"表 {table_number} 第 {row_number} 行第 {column_number} 列")
        if paragraph.cell_paragraph_index is not None:
            display_parts.append(f"单元格第 {paragraph.cell_paragraph_index + 1} 段")
    display_parts.append(f"第 {paragraph_number} 段")
    display_path = " / ".join(display_parts)
    return FindingLocation(
        story=paragraph.story,
        part_name=paragraph.part_name,
        section_path=section_name,
        display_path=display_path,
        paragraph_number=paragraph_number,
        section_name=section_name,
        paragraph_index=paragraph.index,
        table_index=paragraph.table_index,
        row_index=paragraph.row_index,
        column_index=paragraph.column_index,
        cell_paragraph_index=paragraph.cell_paragraph_index,
    )


def paragraph_context(
    document: DocumentModel,
    paragraph: ParagraphNode,
    field: str,
    *,
    expected: Any,
    actual: Any,
) -> dict[str, Any]:
    previous_text = _nearby_text(document, paragraph.index, direction=-1)
    next_text = _nearby_text(document, paragraph.index, direction=1)
    return {
        "style_name": paragraph.style_name,
        "story": paragraph.story,
        "part_name": paragraph.part_name,
        "table_index": paragraph.table_index,
        "row_index": paragraph.row_index,
        "column_index": paragraph.column_index,
        "cell_paragraph_index": paragraph.cell_paragraph_index,
        "field_label": FIELD_LABELS.get(field, field),
        "before_text": paragraph_excerpt(previous_text) if previous_text else None,
        "after_text": paragraph_excerpt(next_text) if next_text else None,
        "expected_value": expected,
        "actual_value": actual,
    }


def paragraph_evidence(
    paragraph: ParagraphNode,
    field: str,
    *,
    expected: Any,
    actual: Any,
    checker_label: str,
) -> str:
    paragraph_number = paragraph.index + 1
    style = paragraph.style_name or "未命名样式"
    excerpt = paragraph_excerpt(paragraph.text)
    field_label = FIELD_LABELS.get(field, field)
    return (
        f"第 {paragraph_number} 段（样式：{style}）{checker_label}“{field_label}”"
        f"与规则不一致：期望 {expected!r}，实际 {actual!r}。原文片段：{excerpt}"
    )


def _nearby_text(document: DocumentModel, paragraph_index: int, *, direction: int) -> str | None:
    index = paragraph_index + direction
    while 0 <= index < len(document.paragraphs):
        text = document.paragraphs[index].text.strip()
        if text:
            return text
        index += direction
    return None
