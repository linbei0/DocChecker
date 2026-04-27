import re
from dataclasses import dataclass

from docchecker.domain.enums import RuleCategory, Severity, SourceType
from docchecker.domain.rules import (
    ExtractionSummary,
    FormatRule,
    RuleSource,
    RuleTarget,
    UnsupportedRequirement,
)


@dataclass(frozen=True)
class RuleExtractionResult:
    rules: list[FormatRule]
    parse_warnings: list[str]
    extraction_summary: ExtractionSummary
    unsupported_requirements: list[UnsupportedRequirement]


@dataclass(frozen=True)
class RequirementChunk:
    text: str
    location: str | None = None


FONT_SIZE_BY_NAME = {
    "初号": 42,
    "小初": 36,
    "一号": 26,
    "小一": 24,
    "二号": 22,
    "小二": 18,
    "三号": 16,
    "小三": 15,
    "四号": 14,
    "小四": 12,
    "五号": 10.5,
    "小五": 9,
    "六号": 7.5,
    "小六": 6.5,
    "七号": 5.5,
    "八号": 5,
}

ALL_RULE_CATEGORIES = list(RuleCategory)
CHECKABLE_CATEGORIES = {
    RuleCategory.page,
    RuleCategory.font,
    RuleCategory.paragraph,
    RuleCategory.heading,
}
UNSUPPORTED_CATEGORY_KEYWORDS = {
    RuleCategory.header_footer: ["页眉", "页脚"],
    RuleCategory.caption: ["图题", "表题", "题注", "图表"],
    RuleCategory.reference: ["参考文献", "著录", "GB/T", "引用"],
    RuleCategory.structure: ["封面", "原创性声明", "致谢", "章", "节", "编号"],
    RuleCategory.toc: ["目录", "目次"],
}
SUPPORTED_REQUIREMENT_KEYWORDS = [
    "正文",
    "行距",
    "首行缩进",
    "页边距",
    "一级标题",
    "二级标题",
    "三级标题",
    "论文题目",
    "中文论文题目",
    "学士学位论文",
    "摘要",
    "关键词",
    "段前",
    "段后",
    "A4",
]


def extract_rules_from_text(text: str, *, source_type: SourceType) -> RuleExtractionResult:
    chunks = _split_requirement_chunks(text)
    if not chunks:
        return RuleExtractionResult(
            rules=[],
            parse_warnings=["规则来源文本为空，未生成候选规则。"],
            extraction_summary=_summary([], []),
            unsupported_requirements=[],
        )

    rules: list[FormatRule] = []
    rules.extend(_extract_body_font_rules(chunks, source_type))
    rules.extend(_extract_line_spacing_rules(chunks, source_type))
    rules.extend(_extract_first_line_indent_rules(chunks, source_type))
    rules.extend(_extract_paragraph_spacing_rules(chunks, source_type))
    rules.extend(_extract_alignment_rules(chunks, source_type))
    rules.extend(_extract_page_rules(chunks, source_type))
    rules.extend(_extract_heading_rules(chunks, source_type))
    rules.extend(_extract_title_rules(chunks, source_type))
    rules.extend(_extract_named_font_rules(chunks, source_type))

    deduped_rules = _dedupe_rules(rules)
    unsupported = _extract_unsupported_requirements(chunks, deduped_rules)
    warnings = _build_warnings(chunks, deduped_rules, unsupported)
    return RuleExtractionResult(
        rules=deduped_rules,
        parse_warnings=warnings,
        extraction_summary=_summary(deduped_rules, unsupported, chunks),
        unsupported_requirements=unsupported,
    )


def _extract_body_font_rules(
    chunks: list[RequirementChunk],
    source_type: SourceType,
) -> list[FormatRule]:
    rules: list[FormatRule] = []
    for chunk in _chunks_containing(chunks, ["正文"]):
        expectation = _font_expectation(chunk.text)
        if expectation:
            rules.append(
                _rule(
                    "body_font",
                    RuleCategory.font,
                    "body.paragraph",
                    "正文",
                    expectation,
                    chunk,
                    source_type,
                    Severity.major,
                )
            )
    return rules


def _extract_line_spacing_rules(
    chunks: list[RequirementChunk],
    source_type: SourceType,
) -> list[FormatRule]:
    rules: list[FormatRule] = []
    for chunk in _chunks_containing(chunks, ["行距"]):
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:倍)?行距", chunk.text)
        if not match:
            continue
        scope, selector = _paragraph_target(chunk.text)
        rules.append(
            _rule(
                _scoped_rule_id(scope, "line_spacing"),
                RuleCategory.paragraph,
                scope,
                selector,
                {"lineSpacing": float(match.group(1))},
                chunk,
                source_type,
                Severity.major,
            )
        )
    return rules


def _extract_first_line_indent_rules(
    chunks: list[RequirementChunk],
    source_type: SourceType,
) -> list[FormatRule]:
    rules: list[FormatRule] = []
    for chunk in _chunks_containing(chunks, ["首行缩进"]):
        match = re.search(r"首行缩进\s*([0-9]+(?:\.[0-9]+)?)\s*(?:字符|字)", chunk.text)
        if not match:
            continue
        # 中文论文规范常用“2 字符”，按小四正文约 0.74cm 估算，报告中保留来源证据。
        indent_cm = round(float(match.group(1)) * 0.37, 2)
        scope, selector = _paragraph_target(chunk.text)
        rules.append(
            _rule(
                _scoped_rule_id(scope, "first_line_indent"),
                RuleCategory.paragraph,
                scope,
                selector,
                {"firstLineIndentCm": indent_cm},
                chunk,
                source_type,
                Severity.major,
            )
        )
    return rules


def _extract_paragraph_spacing_rules(
    chunks: list[RequirementChunk],
    source_type: SourceType,
) -> list[FormatRule]:
    rules: list[FormatRule] = []
    for chunk in _chunks_containing(chunks, ["段前", "段后"]):
        expectation: dict[str, object] = {}
        before_match = re.search(r"段前\s*([0-9]+(?:\.[0-9]+)?)\s*(?:pt|磅)", chunk.text, re.I)
        after_match = re.search(r"段后\s*([0-9]+(?:\.[0-9]+)?)\s*(?:pt|磅)", chunk.text, re.I)
        if before_match:
            expectation["spaceBeforePt"] = float(before_match.group(1))
        if after_match:
            expectation["spaceAfterPt"] = float(after_match.group(1))
        if expectation:
            scope, selector = _paragraph_target(chunk.text)
            rules.append(
                _rule(
                    _scoped_rule_id(scope, "paragraph_spacing"),
                    RuleCategory.paragraph,
                    scope,
                    selector,
                    expectation,
                    chunk,
                    source_type,
                    Severity.minor,
                )
            )
    return rules


def _extract_alignment_rules(
    chunks: list[RequirementChunk],
    source_type: SourceType,
) -> list[FormatRule]:
    rules: list[FormatRule] = []
    for chunk in _chunks_containing(chunks, ["居中", "左对齐", "右对齐", "两端对齐"]):
        alignment = _alignment_value(chunk.text)
        if not alignment:
            continue
        scope, selector = _paragraph_target(chunk.text)
        if scope == "body.paragraph":
            continue
        rules.append(
            _rule(
                _scoped_rule_id(scope, "alignment"),
                RuleCategory.paragraph,
                scope,
                selector,
                {"alignment": alignment},
                chunk,
                source_type,
                Severity.minor,
            )
        )
    return rules


def _extract_page_rules(
    chunks: list[RequirementChunk],
    source_type: SourceType,
) -> list[FormatRule]:
    rules: list[FormatRule] = []
    for chunk in _chunks_containing(chunks, ["页边距", "A4", "页眉", "页脚"]):
        if "A4" in chunk.text.upper():
            rules.append(
                _page_rule(
                    "page_size_a4",
                    {"page_width_cm": 21.0, "page_height_cm": 29.7},
                    chunk,
                    source_type,
                )
            )
        pair_match = re.search(r"页边距.*?上下\s*([0-9]+(?:\.[0-9]+)?)\s*cm", chunk.text, re.I)
        if pair_match:
            value = float(pair_match.group(1))
            rules.extend(
                [
                    _page_rule("page_margin_top", {"margin_top_cm": value}, chunk, source_type),
                    _page_rule(
                        "page_margin_bottom",
                        {"margin_bottom_cm": value},
                        chunk,
                        source_type,
                    ),
                ]
            )
        horizontal_match = re.search(
            r"页边距.*?左右\s*([0-9]+(?:\.[0-9]+)?)\s*cm",
            chunk.text,
            re.I,
        )
        if horizontal_match:
            value = float(horizontal_match.group(1))
            rules.extend(
                [
                    _page_rule("page_margin_left", {"margin_left_cm": value}, chunk, source_type),
                    _page_rule("page_margin_right", {"margin_right_cm": value}, chunk, source_type),
                ]
            )
        for label, field, rule_id in [
            ("上", "margin_top_cm", "page_margin_top"),
            ("下", "margin_bottom_cm", "page_margin_bottom"),
            ("左", "margin_left_cm", "page_margin_left"),
            ("右", "margin_right_cm", "page_margin_right"),
            ("页眉", "header_distance_cm", "page_header_distance"),
            ("页脚", "footer_distance_cm", "page_footer_distance"),
        ]:
            match = re.search(rf"{label}\s*([0-9]+(?:\.[0-9]+)?)\s*cm", chunk.text, re.I)
            if match:
                rules.append(
                    _page_rule(rule_id, {field: float(match.group(1))}, chunk, source_type)
                )
    return rules


def _extract_heading_rules(
    chunks: list[RequirementChunk],
    source_type: SourceType,
) -> list[FormatRule]:
    rules: list[FormatRule] = []
    for label, rule_id, scope, selector in [
        ("一级标题", "heading1_font", "heading.1", "Heading 1"),
        ("二级标题", "heading2_font", "heading.2", "Heading 2"),
        ("三级标题", "heading3_font", "heading.3", "Heading 3"),
    ]:
        for chunk in _chunks_containing(chunks, [label]):
            expectation = _font_expectation(chunk.text)
            alignment = _alignment_value(chunk.text)
            if alignment:
                expectation["alignment"] = alignment
            if expectation:
                rules.append(
                    _rule(
                        rule_id,
                        RuleCategory.heading,
                        scope,
                        selector,
                        expectation,
                        chunk,
                        source_type,
                        Severity.major,
                    )
                )
    return rules


def _extract_title_rules(
    chunks: list[RequirementChunk],
    source_type: SourceType,
) -> list[FormatRule]:
    explicit_chunks = _chunks_containing(chunks, ["论文题目", "中文论文题目", "学士学位论文"])
    fallback_chunks = [
        chunk
        for chunk in _chunks_containing(chunks, ["居中"])
        if _first_font_size(chunk.text) and not explicit_chunks
    ]
    rules: list[FormatRule] = []
    for chunk in explicit_chunks or fallback_chunks:
        expectation = _font_expectation(chunk.text)
        alignment = _alignment_value(chunk.text)
        if alignment:
            expectation["alignment"] = alignment
        if expectation:
            rules.append(
                _rule(
                    "title_format",
                    RuleCategory.font,
                    "cover.title",
                    "论文题目",
                    expectation,
                    chunk,
                    source_type,
                    Severity.major,
                    confidence=0.85 if explicit_chunks else 0.72,
                )
            )
    return rules


def _extract_named_font_rules(
    chunks: list[RequirementChunk],
    source_type: SourceType,
) -> list[FormatRule]:
    rules: list[FormatRule] = []
    for label, rule_id, scope, category in [
        ("摘要", "abstract_font", "abstract.paragraph", RuleCategory.font),
        ("关键词", "keywords_font", "keywords.paragraph", RuleCategory.font),
    ]:
        for chunk in _chunks_containing(chunks, [label]):
            expectation = _font_expectation(chunk.text)
            if expectation:
                rules.append(
                    _rule(
                        rule_id,
                        category,
                        scope,
                        label,
                        expectation,
                        chunk,
                        source_type,
                        Severity.major,
                        confidence=0.78,
                    )
                )
    return rules


def _font_expectation(text: str) -> dict[str, object]:
    expectation: dict[str, object] = {}
    font_family = _first_font_family(text)
    font_size = _first_font_size(text)
    if font_family:
        expectation["fontFamilyEastAsia"] = font_family
    if font_size:
        expectation["fontSizePt"] = font_size
    if "加粗" in text or "黑体" in text:
        expectation["bold"] = True
    return expectation


def _first_font_family(text: str) -> str | None:
    for family in ["宋体", "黑体", "楷体", "楷体_GB2312", "仿宋", "微软雅黑", "Times New Roman"]:
        if family in text:
            return family
    return None


def _first_font_size(text: str) -> float | None:
    for name, value in FONT_SIZE_BY_NAME.items():
        if name in text:
            return value
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:pt|磅)", text, re.I)
    return float(match.group(1)) if match else None


def _alignment_value(text: str) -> str | None:
    if "居中" in text:
        return "center"
    if "右对齐" in text:
        return "right"
    if "左对齐" in text:
        return "left"
    if "两端对齐" in text:
        return "justify"
    return None


def _paragraph_target(text: str) -> tuple[str, str | None]:
    if "摘要" in text:
        return "abstract.paragraph", "摘要"
    if "关键词" in text:
        return "keywords.paragraph", "关键词"
    if "一级标题" in text:
        return "heading.1", "Heading 1"
    if "二级标题" in text:
        return "heading.2", "Heading 2"
    if "三级标题" in text:
        return "heading.3", "Heading 3"
    return "body.paragraph", "正文"


def _scoped_rule_id(scope: str, suffix: str) -> str:
    prefix = scope.replace(".", "_")
    if prefix == "body_paragraph":
        prefix = "body"
    return f"{prefix}_{suffix}"


def _chunks_containing(
    chunks: list[RequirementChunk],
    keywords: list[str],
) -> list[RequirementChunk]:
    return [chunk for chunk in chunks if any(keyword in chunk.text for keyword in keywords)]


def _page_rule(
    rule_id: str,
    expectation: dict[str, object],
    chunk: RequirementChunk,
    source_type: SourceType,
) -> FormatRule:
    tolerance = dict.fromkeys(
        [
            "page_width_cm",
            "page_height_cm",
            "margin_top_cm",
            "margin_bottom_cm",
            "margin_left_cm",
            "margin_right_cm",
            "header_distance_cm",
            "footer_distance_cm",
        ],
        0.1,
    )
    return _rule(
        rule_id,
        RuleCategory.page,
        "document",
        "整篇文档",
        expectation,
        chunk,
        source_type,
        Severity.minor,
        tolerance,
    )


def _rule(
    rule_id: str,
    category: RuleCategory,
    scope: str,
    selector: str | None,
    expectation: dict[str, object],
    chunk: RequirementChunk,
    source_type: SourceType,
    severity: Severity,
    tolerance: dict[str, object] | None = None,
    confidence: float = 0.85,
) -> FormatRule:
    return FormatRule(
        id=rule_id,
        category=category,
        target=RuleTarget(scope=scope, selector=selector),
        expectation=expectation,
        tolerance=tolerance or {},
        severity=severity,
        source=RuleSource(type=source_type, excerpt=chunk.text[:300], location=chunk.location),
        confidence=confidence,
        enabled=True,
    )


def _extract_unsupported_requirements(
    chunks: list[RequirementChunk],
    rules: list[FormatRule],
) -> list[UnsupportedRequirement]:
    unsupported: list[UnsupportedRequirement] = []
    rule_sources = {(rule.source.location, rule.source.excerpt) for rule in rules}
    for chunk in chunks:
        if (chunk.location, chunk.text[:300]) in rule_sources:
            continue
        for category, keywords in UNSUPPORTED_CATEGORY_KEYWORDS.items():
            if (
                category in {RuleCategory.header_footer}
                and _has_checkable_page_header_footer(chunk)
            ):
                continue
            if any(keyword in chunk.text for keyword in keywords):
                reason = (
                    f"已识别到 {category.value} 类要求，"
                    "但当前缺少对应检查器或结构化解析能力。"
                )
                unsupported.append(
                    UnsupportedRequirement(
                        category=category,
                        excerpt=chunk.text[:300],
                        location=chunk.location,
                        reason=reason,
                    )
                )
                break
    return _dedupe_unsupported(unsupported)


def _has_checkable_page_header_footer(chunk: RequirementChunk) -> bool:
    return bool(re.search(r"(页眉|页脚)\s*[0-9]+(?:\.[0-9]+)?\s*cm", chunk.text, re.I))


def _build_warnings(
    chunks: list[RequirementChunk],
    rules: list[FormatRule],
    unsupported: list[UnsupportedRequirement],
) -> list[str]:
    warnings: list[str] = []
    if not rules:
        warnings.append("未识别到可自动校验的格式规则，请补充字体、字号、行距、缩进或页边距要求。")
    for item in unsupported:
        location = f"{item.location}：" if item.location else ""
        warnings.append(f"{location}{item.reason}")
    low_confidence = [rule for rule in rules if rule.confidence < 0.8]
    if low_confidence:
        warnings.append(f"有 {len(low_confidence)} 条规则置信度较低，请在确认页重点核对。")
    if not rules and not unsupported and chunks:
        warnings.append("规范文本已读取，但未命中当前规则能力矩阵中的格式要求。")
    return warnings


def _summary(
    rules: list[FormatRule],
    unsupported: list[UnsupportedRequirement],
    chunks: list[RequirementChunk] | None = None,
) -> ExtractionSummary:
    supported_categories = sorted({rule.category for rule in rules}, key=lambda item: item.value)
    unsupported_categories = sorted(
        {item.category for item in unsupported},
        key=lambda item: item.value,
    )
    present_categories = set(supported_categories) | set(unsupported_categories)
    uncovered = sorted(set(ALL_RULE_CATEGORIES) - present_categories, key=lambda item: item.value)
    return ExtractionSummary(
        total_requirements=_count_requirement_candidates(chunks or [], rules, unsupported),
        structured_rules=len(rules),
        unsupported_requirements=len(unsupported),
        low_confidence_rules=len([rule for rule in rules if rule.confidence < 0.8]),
        supported_categories=supported_categories,
        unsupported_categories=unsupported_categories,
        uncovered_categories=uncovered,
    )


def _count_requirement_candidates(
    chunks: list[RequirementChunk],
    rules: list[FormatRule],
    unsupported: list[UnsupportedRequirement],
) -> int:
    if not chunks:
        return len(rules) + len(unsupported)
    count = 0
    for chunk in chunks:
        if any(keyword in chunk.text for keyword in SUPPORTED_REQUIREMENT_KEYWORDS):
            count += 1
            continue
        if any(
            keyword in chunk.text
            for keywords in UNSUPPORTED_CATEGORY_KEYWORDS.values()
            for keyword in keywords
        ):
            count += 1
    return max(count, len(rules) + len(unsupported))


def _split_requirement_chunks(text: str) -> list[RequirementChunk]:
    chunks: list[RequirementChunk] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        location, content = _parse_location_prefix(line)
        parts = [part.strip() for part in re.split(r"[。；;]", content) if part.strip()]
        if not parts:
            parts = [content]
        for part_index, part in enumerate(parts, start=1):
            part_location = location
            if location and len(parts) > 1:
                part_location = f"{location},part:{part_index}"
            chunks.append(RequirementChunk(text=part, location=part_location))
    if not chunks:
        normalized = re.sub(r"\s+", " ", text.strip())
        chunks.extend(
            RequirementChunk(text=part.strip())
            for part in re.split(r"[。；;\n\r]", normalized)
            if part.strip()
        )
    return chunks


def _parse_location_prefix(line: str) -> tuple[str | None, str]:
    match = re.match(r"^((?:paragraph|table|comment):[^\t]+)\t(.+)$", line)
    if not match:
        return None, line
    return match.group(1), match.group(2).strip()


def _dedupe_rules(rules: list[FormatRule]) -> list[FormatRule]:
    seen: set[tuple[str, str | None]] = set()
    deduped: list[FormatRule] = []
    for rule in rules:
        key = (rule.id, rule.source.location)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(rule)
    return deduped


def _dedupe_unsupported(items: list[UnsupportedRequirement]) -> list[UnsupportedRequirement]:
    seen: set[tuple[RuleCategory, str | None, str]] = set()
    deduped: list[UnsupportedRequirement] = []
    for item in items:
        key = (item.category, item.location, item.excerpt)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
