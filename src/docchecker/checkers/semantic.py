import re
from collections.abc import Iterable

from docchecker.checkers.base import relevant_rules
from docchecker.domain.document import DocumentModel, ParagraphNode
from docchecker.domain.enums import RuleCategory
from docchecker.domain.findings import CheckFinding, FindingLocation
from docchecker.domain.rules import FormatRule


class StructureChecker:
    checker_id = "structure_checker"
    supported_categories = {RuleCategory.structure}

    def check(self, document: DocumentModel, rules: list[FormatRule]) -> list[CheckFinding]:
        findings: list[CheckFinding] = []
        paragraphs = _nonempty_paragraphs(document)
        text = "\n".join(paragraph.text for paragraph in paragraphs)
        for rule in relevant_rules(rules, self.supported_categories):
            required = rule.expectation.get("requiredSections", [])
            if not isinstance(required, list):
                continue
            missing = [
                section
                for section in required
                if isinstance(section, str)
                and _section_index(section, document, text, paragraphs) is None
            ]
            if missing:
                findings.append(
                    _document_finding(
                        rule,
                        self.checker_id,
                        {"missingSections": []},
                        {"missingSections": missing},
                        f"论文缺少必要结构：{', '.join(missing)}。",
                        "请补齐缺失的论文结构，或在规则确认页关闭不适用的结构规则。",
                        excerpt=_document_excerpt(paragraphs),
                    )
                )
                continue
            order_problem = _first_order_problem(required, document, text, paragraphs)
            if order_problem:
                findings.append(
                    _document_finding(
                        rule,
                        self.checker_id,
                        {"sectionOrder": required},
                        {"outOfOrder": order_problem},
                        f"论文结构顺序不符合规则：{order_problem}。",
                        "请按规则要求调整论文组成部分的先后顺序。",
                        excerpt=_document_excerpt(paragraphs),
                    )
                )
        return findings


class TocChecker:
    checker_id = "toc_checker"
    supported_categories = {RuleCategory.toc}

    def check(self, document: DocumentModel, rules: list[FormatRule]) -> list[CheckFinding]:
        findings: list[CheckFinding] = []
        paragraphs = _nonempty_paragraphs(document)
        toc_entries = [
            paragraph
            for paragraph in paragraphs
            if (
                paragraph.style_name
                and "toc" in paragraph.style_name.lower()
                or bool(re.match(r"^\d+(?:\.\d+){0,3}\s+.+\s+\d+$", paragraph.text))
            )
        ]
        has_toc_title = any(paragraph.text.replace(" ", "") == "目录" for paragraph in paragraphs)
        for rule in relevant_rules(rules, self.supported_categories):
            if rule.expectation.get("requiresToc") and not has_toc_title:
                findings.append(
                    _document_finding(
                        rule,
                        self.checker_id,
                        {"requiresToc": True},
                        {"requiresToc": False},
                        "论文未检测到目录标题。",
                        "请生成或补充目录，并确认目录标题为“目录”。",
                    )
                )
            if rule.expectation.get("requiresEntries") and not toc_entries:
                findings.append(
                    _document_finding(
                        rule,
                        self.checker_id,
                        {"tocEntries": "编号 + 标题 + 页码"},
                        {"tocEntries": "未检测到目录项"},
                        "论文未检测到符合基本形态的目录项。",
                        "请检查目录是否自动生成，至少包含编号、标题和页码列。",
                    )
                )
        return findings


class CaptionChecker:
    checker_id = "caption_checker"
    supported_categories = {RuleCategory.caption}

    def check(self, document: DocumentModel, rules: list[FormatRule]) -> list[CheckFinding]:
        findings: list[CheckFinding] = []
        captions = [
            paragraph
            for paragraph in _nonempty_paragraphs(document)
            if re.match(r"^[图表]\s*\d+(?:[.-]\d+)*", paragraph.text)
        ]
        for rule in relevant_rules(rules, self.supported_categories):
            invalid = [
                paragraph
                for paragraph in captions
                if not re.match(r"^[图表]\d+(?:\.\d+)+\s+\S+", paragraph.text)
            ]
            for paragraph in invalid:
                findings.append(
                    _paragraph_finding(
                        rule,
                        self.checker_id,
                        paragraph,
                        {"captionPattern": "图1.1 题名 / 表1.1 题名"},
                        {"caption": paragraph.text},
                        f"题注编号或空格格式不符合规则：{paragraph.text}",
                        "请按“图1.1 题名”或“表1.1 题名”的格式调整题注。",
                    )
                )
        return findings


class ReferenceChecker:
    checker_id = "reference_checker"
    supported_categories = {RuleCategory.reference}

    def check(self, document: DocumentModel, rules: list[FormatRule]) -> list[CheckFinding]:
        findings: list[CheckFinding] = []
        paragraphs = _nonempty_paragraphs(document)
        references = [
            paragraph for paragraph in paragraphs if re.match(r"^\[\d+\]", paragraph.text)
        ]
        for rule in relevant_rules(rules, self.supported_categories):
            if rule.expectation.get("requiresReferences") and not references:
                findings.append(
                    _document_finding(
                        rule,
                        self.checker_id,
                        {"references": "至少 1 条编号参考文献"},
                        {"references": "未检测到编号参考文献"},
                        "论文未检测到形如 [1] 的参考文献条目。",
                        "请检查参考文献部分是否存在，并按编号顺序列出。",
                    )
                )
                continue
            expected = list(range(1, len(references) + 1))
            actual = [_reference_number(paragraph.text) for paragraph in references]
            if actual != expected:
                findings.append(
                    _document_finding(
                        rule,
                        self.checker_id,
                        {"referenceOrder": expected},
                        {"referenceOrder": actual},
                        "参考文献编号不连续或顺序异常。",
                        "请按正文引用出现顺序或规范要求重新编号参考文献。",
                    )
                )
            for paragraph in references:
                if len(paragraph.text.split(".", maxsplit=1)) < 2 and "，" not in paragraph.text:
                    findings.append(
                        _paragraph_finding(
                            rule,
                            self.checker_id,
                            paragraph,
                            {"referenceEntry": "编号 + 作者/题名/来源信息"},
                            {"referenceEntry": paragraph.text},
                            f"参考文献条目信息可能不完整：{paragraph.text}",
                            "请补充作者、题名、来源、年份等基本著录信息。",
                        )
                    )
        return findings


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
