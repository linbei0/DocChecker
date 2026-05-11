import re
from dataclasses import dataclass

from docchecker.domain.enums import RuleCategory, Severity, SourceType
from docchecker.domain.requirements import RequirementBlock
from docchecker.domain.rules import ExtractedRuleCandidate, FormatRule
from docchecker.services.rule_extractor_factory import _page_rule, _rule
from docchecker.services.rule_extractor_semantic import _local_rule_candidates
from docchecker.services.rule_extractor_style import (
    _extract_exemplar_rules,
    _extract_style_cluster_rules,
)
from docchecker.services.rule_extractor_targeting import (
    _has_explicit_non_body_target,
    _has_non_body_format_context,
)
from docchecker.services.rule_extractor_types import RequirementChunk

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
@dataclass(frozen=True)
class LocalRuleExtraction:
    rules: list[FormatRule]
    candidates: list[ExtractedRuleCandidate]


def extract_local_rules(
    chunks: list[RequirementChunk],
    *,
    source_type: SourceType,
    blocks: list[RequirementBlock] | None = None,
) -> LocalRuleExtraction:
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
    if blocks:
        rules.extend(_extract_style_cluster_rules(blocks, source_type))
        rules.extend(_extract_exemplar_rules(blocks, source_type))
    return LocalRuleExtraction(rules=rules, candidates=_local_rule_candidates(chunks))


def _extract_body_font_rules(
    chunks: list[RequirementChunk],
    source_type: SourceType,
) -> list[FormatRule]:
    rules: list[FormatRule] = []
    for chunk in _body_rule_chunks(chunks):
        expectation = _font_expectation(chunk.text)
        if expectation:
            rules.append(
                _rule(
                    "body_font",
                    RuleCategory.font,
                    "body.paragraph",
                    None,
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
        scope, selector = _paragraph_target(chunk.text, chunk.target_hint)
        if _should_skip_default_body_paragraph_rule(scope, chunk):
            continue
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
        match = re.search(
            r"首行缩进\s*([0-9]+(?:\.[0-9]+)?)\s*(?:个)?(?:字符|字)",
            chunk.text,
        )
        if not match:
            continue
        # 中文论文规范常用“2 字符”，按小四正文约 0.74cm 估算，报告中保留来源证据。
        indent_cm = round(float(match.group(1)) * 0.37, 2)
        scope, selector = _paragraph_target(chunk.text, chunk.target_hint)
        if _should_skip_default_body_paragraph_rule(scope, chunk):
            continue
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
                    tolerance={"firstLineIndentCm": 0.15},
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
            scope, selector = _paragraph_target(chunk.text, chunk.target_hint)
            if _should_skip_default_body_paragraph_rule(scope, chunk):
                continue
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
        scope, selector = _paragraph_target(chunk.text, chunk.target_hint)
        if scope == "body.paragraph" and chunk.target_hint != "body.paragraph":
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
                        confidence=0.86,
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


def _paragraph_target(
    text: str,
    target_hint: str | None = None,
) -> tuple[str, str | None]:
    if target_hint == "body.paragraph" and not _has_explicit_non_body_target(text):
        return "body.paragraph", None
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
    return "body.paragraph", None


def _should_skip_default_body_paragraph_rule(
    scope: str,
    chunk: RequirementChunk,
) -> bool:
    if scope != "body.paragraph":
        return False
    if _has_non_body_format_context(chunk.text):
        return True
    return bool(
        chunk.location
        and chunk.location.startswith("comment:")
        and chunk.target_hint != "body.paragraph"
        and "正文" not in chunk.text
    )


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


def _body_rule_chunks(chunks: list[RequirementChunk]) -> list[RequirementChunk]:
    return [
        chunk
        for chunk in chunks
        if "正文" in chunk.text or chunk.target_hint == "body.paragraph"
    ]
