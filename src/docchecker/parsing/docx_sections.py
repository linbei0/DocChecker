import re

from docchecker.domain.document import LogicalSectionNode, ParagraphNode


def _is_heading_style(style_name: str | None) -> bool:
    if not style_name:
        return False
    normalized = style_name.strip().lower()
    return normalized.startswith("heading") or normalized.startswith("标题")


def _compact_text(text: str, *, max_length: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[: max_length - 1]}…"


SECTION_ROLE_ALIASES = {
    "abstract": ("中文摘要", "摘要", "摘 要", "abstract"),
    "keywords": ("中文关键词", "关键词", "关键字", "keywords", "key words"),
    "toc": ("目录", "目 录", "目  录"),
    "body": ("正文",),
    "acknowledgements": ("致谢", "致 谢", "谢辞"),
    "references": ("参考文献", "references", "bibliography"),
    "appendix": ("附录", "appendix"),
}


def _is_known_section_title(text: str) -> bool:
    normalized = _normalize_section_text(text)
    return any(
        normalized == _normalize_section_text(alias)
        for aliases in SECTION_ROLE_ALIASES.values()
        for alias in aliases
    )


def _build_logical_sections(paragraphs: list[ParagraphNode]) -> list[LogicalSectionNode]:
    sections: list[LogicalSectionNode] = []
    for paragraph in paragraphs:
        role = _section_role(paragraph)
        if role is None:
            continue
        title = _compact_text(paragraph.text.strip(), max_length=80)
        if sections and sections[-1].role == role:
            continue
        if sections and sections[-1].end_paragraph_index is None:
            sections[-1].end_paragraph_index = paragraph.index - 1
        sections.append(
            LogicalSectionNode(
                role=role,
                title=title,
                start_paragraph_index=paragraph.index,
            )
        )
    if sections and sections[-1].end_paragraph_index is None:
        sections[-1].end_paragraph_index = paragraphs[-1].index if paragraphs else 0
    return sections


def _section_role(paragraph: ParagraphNode) -> str | None:
    text = paragraph.text.strip()
    if not text or _is_toc_entry(paragraph):
        return None
    normalized = _normalize_section_text(text)
    for role, aliases in SECTION_ROLE_ALIASES.items():
        for alias in aliases:
            alias_text = _normalize_section_text(alias)
            if normalized == alias_text or normalized.startswith(alias_text):
                return role
    if _is_heading_style(paragraph.style_name):
        return "body"
    if re.match(r"^\d+(?:\.\d+){0,3}\s+\S{1,80}$", text):
        return "body"
    return None


def _is_toc_entry(paragraph: ParagraphNode) -> bool:
    style_name = (paragraph.style_name or "").lower()
    if style_name.startswith("toc") or "目录" in style_name:
        return _normalize_section_text(paragraph.text) != _normalize_section_text("目录")
    return bool(re.match(r"^\d+(?:\.\d+){0,3}\s+.+\s+\d+$", paragraph.text.strip()))


def _normalize_section_text(value: str) -> str:
    return re.sub(r"[\s　:：]+", "", value).lower()
