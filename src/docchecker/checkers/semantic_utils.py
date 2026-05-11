import re
from collections.abc import Iterable

from docchecker.domain.document import DocumentModel, ParagraphNode
from docchecker.domain.findings import CheckFinding, FindingLocation
from docchecker.domain.rules import FormatRule


def _nonempty_paragraphs(document: DocumentModel) -> list[ParagraphNode]:
    return [paragraph for paragraph in document.paragraphs if paragraph.text.strip()]


SECTION_ALIASES = {
    "中文摘要": ["中文摘要", "摘要", "摘 要"],
    "中文关键词": ["中文关键词", "关键词", "关键字"],
    "英文摘要": ["英文摘要", "Abstract"],
    "英文关键词": ["英文关键词", "Keywords", "Key words"],
    "目录": ["目录", "目 录", "目  录"],
    "正文": ["正文"],
}

SECTION_ROLE_BY_REQUIREMENT = {
    "中文摘要": "abstract",
    "摘要": "abstract",
    "英文摘要": "abstract",
    "中文关键词": "keywords",
    "关键词": "keywords",
    "英文关键词": "keywords",
    "目录": "toc",
    "正文": "body",
    "致谢": "acknowledgements",
    "参考文献": "references",
    "附录": "appendix",
}


def _first_order_problem(
    required: Iterable[object],
    document: DocumentModel,
    text: str,
    paragraphs: list[ParagraphNode],
) -> str | None:
    last_index = -1
    last_section = ""
    for section in required:
        if not isinstance(section, str):
            continue
        index = _section_index(section, document, text, paragraphs)
        if index is None:
            continue
        if index < last_index:
            return f"{section} 出现在 {last_section} 之前"
        last_index = index
        last_section = section
    return None


def _section_index(
    section: str,
    document: DocumentModel,
    text: str,
    paragraphs: list[ParagraphNode],
) -> int | None:
    role = _section_role_for_requirement(section)
    if role:
        matches = [
            item.start_paragraph_index
            for item in document.logical_sections
            if item.role == role
        ]
        if matches:
            return min(matches)

    if section == "正文" and _has_body_content(paragraphs):
        first_heading = next(
            (
                paragraph
                for paragraph in paragraphs
                if _is_heading_paragraph(paragraph) and not _is_toc_paragraph(paragraph)
            ),
            None,
        )
        return first_heading.index if first_heading else 0

    matches = [
        paragraph.index
        for paragraph in paragraphs
        if _paragraph_matches_section(paragraph, section)
    ]
    return min(matches) if matches else None


def _paragraph_matches_section(paragraph: ParagraphNode, section: str) -> bool:
    if _is_toc_paragraph(paragraph) and section != "目录":
        return False
    paragraph_text = _normalize_text(paragraph.text)
    if not paragraph_text:
        return False
    for alias in SECTION_ALIASES.get(section, [section]):
        alias_text = _normalize_text(alias)
        if not alias_text:
            continue
        if _is_heading_paragraph(paragraph) or section in {"致谢", "参考文献", "目录"}:
            if paragraph_text == alias_text or paragraph_text.startswith(alias_text):
                return True
            continue
        if paragraph_text.startswith(alias_text):
            return True
    return False


def _section_role_for_requirement(section: str) -> str | None:
    normalized = _normalize_text(section)
    for name, role in SECTION_ROLE_BY_REQUIREMENT.items():
        if normalized == _normalize_text(name):
            return role
    return None


def _has_body_content(paragraphs: list[ParagraphNode]) -> bool:
    return any(_is_heading_paragraph(paragraph) for paragraph in paragraphs)


def _is_heading_paragraph(paragraph: ParagraphNode) -> bool:
    style_name = (paragraph.style_name or "").lower()
    return style_name.startswith("heading")


def _is_toc_paragraph(paragraph: ParagraphNode) -> bool:
    style_name = (paragraph.style_name or "").lower()
    return style_name.startswith("toc") or "目录" in style_name


def _normalize_text(value: str) -> str:
    return re.sub(r"[\s　:：]+", "", value).lower()


def _valid_caption_text(text: str) -> bool:
    return bool(re.match(r"^\s*[图表]\s*\d+(?:\.\d+)+\s+\S+", text))


def _document_excerpt(paragraphs: list[ParagraphNode]) -> str | None:
    snippets = [
        paragraph.text.strip()
        for paragraph in paragraphs
        if paragraph.text.strip()
        and (_is_heading_paragraph(paragraph) or len(paragraph.text) <= 80)
    ]
    if not snippets:
        snippets = [paragraph.text.strip() for paragraph in paragraphs if paragraph.text.strip()]
    if not snippets:
        return None
    return "；".join(snippets[:8])[:300]


def _reference_number(text: str) -> int | None:
    match = re.match(r"^\[(\d+)\]", text)
    return int(match.group(1)) if match else None


def _document_finding(
    rule: FormatRule,
    checker_id: str,
    expected: dict[str, object],
    actual: dict[str, object],
    evidence: str,
    suggestion: str,
    excerpt: str | None = None,
) -> CheckFinding:
    return CheckFinding(
        id=f"{rule.id}:document",
        rule_id=rule.id,
        checker_id=checker_id,
        category=rule.category,
        severity=rule.severity,
        location=FindingLocation(area="document", display_path="整篇文档"),
        expected=expected,
        actual=actual,
        excerpt=excerpt,
        evidence=evidence,
        suggestion=suggestion,
    )


def _paragraph_finding(
    rule: FormatRule,
    checker_id: str,
    paragraph: ParagraphNode,
    expected: dict[str, object],
    actual: dict[str, object],
    evidence: str,
    suggestion: str,
) -> CheckFinding:
    paragraph_number = paragraph.index + 1
    return CheckFinding(
        id=f"{rule.id}:paragraph-{paragraph.index}",
        rule_id=rule.id,
        checker_id=checker_id,
        category=rule.category,
        severity=rule.severity,
        location=FindingLocation(
            display_path=f"第 {paragraph_number} 段",
            paragraph_number=paragraph_number,
            paragraph_index=paragraph.index,
        ),
        expected=expected,
        actual=actual,
        excerpt=paragraph.text[:120],
        evidence=evidence,
        suggestion=suggestion,
    )


def _abstract_count_finding(
    rule: FormatRule,
    fact,
    expected: dict[str, object],
) -> CheckFinding:
    return CheckFinding(
        id=f"{rule.id}:abstract-{fact.language}:{next(iter(expected))}",
        rule_id=rule.id,
        checker_id="abstract_checker",
        category=rule.category,
        severity=rule.severity,
        location=FindingLocation(
            display_path=f"{'中文' if fact.language == 'zh' else '英文'}摘要",
            paragraph_index=fact.title_paragraph_index,
            paragraph_number=fact.title_paragraph_index + 1,
        ),
        expected=expected,
        actual={"wordCount": fact.word_count},
        excerpt=fact.content_text[:120],
        evidence="摘要字数不符合规则要求。",
        suggestion="请按规范调整摘要篇幅。",
    )


def _abstract_word_count_rule_applies(rule: FormatRule, language: str) -> bool:
    source_text = f"{rule.target.selector or ''} {rule.source.excerpt}"
    if _mentions_chinese_abstract(source_text) and not _mentions_english_abstract(source_text):
        return language == "zh"
    if _mentions_english_abstract(source_text) and not _mentions_chinese_abstract(source_text):
        return language == "en"
    return True


def _mentions_chinese_abstract(text: str) -> bool:
    return "中文摘要" in text or "摘 要" in text


def _mentions_english_abstract(text: str) -> bool:
    return "英文摘要" in text or "Abstract" in text
