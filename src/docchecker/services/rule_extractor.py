import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from pydantic import TypeAdapter, ValidationError

from docchecker.core.config import get_settings
from docchecker.domain.enums import RuleCategory, Severity, SourceType
from docchecker.domain.requirements import RequirementBlock, RequirementDocumentModel
from docchecker.domain.rules import (
    ExtractedRuleCandidate,
    ExtractionSummary,
    FormatRule,
    RuleExtractionIssue,
    RuleExtractionTrace,
    RuleSource,
    RuleTarget,
    UnsupportedRequirement,
)
from docchecker.services.rule_compiler import compile_rule_candidates


@dataclass(frozen=True)
class RuleExtractionResult:
    rules: list[FormatRule]
    suggested_rules: list[FormatRule]
    parse_warnings: list[str]
    extraction_summary: ExtractionSummary
    unsupported_requirements: list[UnsupportedRequirement]
    extraction_trace: RuleExtractionTrace


@dataclass(frozen=True)
class RequirementChunk:
    text: str
    location: str | None = None
    target_hint: str | None = None
    evidence_type: str = "explicit_text"


class RuleExtractionConfigurationError(RuntimeError):
    """规则抽取配置缺失或不可用。"""


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
UNSUPPORTED_CATEGORY_KEYWORDS = {
    RuleCategory.header_footer: ["页眉", "页脚"],
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
        trace = RuleExtractionTrace(mode=get_settings().rule_extractor_mode)
        return RuleExtractionResult(
            rules=[],
            suggested_rules=[],
            parse_warnings=["规则来源文本为空，未生成候选规则。"],
            extraction_summary=_summary([], []),
            unsupported_requirements=[],
            extraction_trace=trace,
        )
    return _extract_rules_from_chunks(chunks, source_type=source_type)


def extract_rules_from_requirement_document(
    document: RequirementDocumentModel,
    *,
    source_type: SourceType,
) -> RuleExtractionResult:
    chunks = [
        RequirementChunk(
            text=block.text,
            location=block.location,
            target_hint=_block_target_hint(block),
            evidence_type=_block_evidence_type(block),
        )
        for block in document.blocks
        if block.text.strip()
    ]
    if not chunks:
        trace = RuleExtractionTrace(mode=get_settings().rule_extractor_mode)
        return RuleExtractionResult(
            rules=[],
            suggested_rules=[],
            parse_warnings=["规则来源文档没有可解析文本块，未生成候选规则。"],
            extraction_summary=_summary([], []),
            unsupported_requirements=[],
            extraction_trace=trace,
        )
    return _extract_rules_from_chunks(chunks, source_type=source_type, blocks=document.blocks)


def _extract_rules_from_chunks(
    chunks: list[RequirementChunk],
    *,
    source_type: SourceType,
    blocks: list[RequirementBlock] | None = None,
) -> RuleExtractionResult:
    settings = get_settings()
    candidates = _local_rule_candidates(chunks)
    issues: list[RuleExtractionIssue] = []
    if settings.rule_extractor_mode == "hybrid":
        llm_candidates, llm_issues = _llm_rule_candidates(blocks or _blocks_from_chunks(chunks))
        candidates.extend(llm_candidates)
        issues.extend(llm_issues)

    extracted_rules: list[FormatRule] = []
    extracted_rules.extend(_extract_body_font_rules(chunks, source_type))
    extracted_rules.extend(_extract_line_spacing_rules(chunks, source_type))
    extracted_rules.extend(_extract_first_line_indent_rules(chunks, source_type))
    extracted_rules.extend(_extract_paragraph_spacing_rules(chunks, source_type))
    extracted_rules.extend(_extract_alignment_rules(chunks, source_type))
    extracted_rules.extend(_extract_page_rules(chunks, source_type))
    extracted_rules.extend(_extract_heading_rules(chunks, source_type))
    extracted_rules.extend(_extract_title_rules(chunks, source_type))
    extracted_rules.extend(_extract_named_font_rules(chunks, source_type))
    if blocks:
        extracted_rules.extend(_extract_style_cluster_rules(blocks, source_type))
        extracted_rules.extend(_extract_exemplar_rules(blocks, source_type))
    compilation = compile_rule_candidates(candidates, source_type=source_type)
    combined_rules = extracted_rules + compilation.rules + compilation.suggested_rules
    combined_rules, conflict_issues = _move_conflicting_rules_to_confirmation(combined_rules)
    auto_rules, suggested_rules = _split_rules_by_confirmation(combined_rules)
    issues.extend(compilation.issues)
    issues.extend(conflict_issues)
    deduped_rules = _dedupe_rules(auto_rules)
    deduped_suggested_rules = _dedupe_rules(suggested_rules)
    unsupported = _extract_unsupported_requirements(
        chunks,
        deduped_rules + deduped_suggested_rules,
        issues,
    )
    warnings = _build_warnings(
        chunks,
        deduped_rules,
        deduped_suggested_rules,
        unsupported,
    )
    trace = RuleExtractionTrace(
        mode=settings.rule_extractor_mode,
        candidates=candidates,
        issues=issues,
    )
    return RuleExtractionResult(
        rules=deduped_rules,
        suggested_rules=deduped_suggested_rules,
        parse_warnings=warnings,
        extraction_summary=_summary(
            deduped_rules,
            unsupported,
            chunks,
            suggested_rules=deduped_suggested_rules,
            issues=issues,
        ),
        unsupported_requirements=unsupported,
        extraction_trace=trace,
    )


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


def _extract_style_cluster_rules(
    blocks: list[RequirementBlock],
    source_type: SourceType,
) -> list[FormatRule]:
    clusters: dict[tuple[tuple[str, object], ...], list[RequirementBlock]] = {}
    for block in blocks:
        if block.type != "paragraph" or "正文段落" not in block.text:
            continue
        formatting = block.context.get("formatting")
        if not isinstance(formatting, dict):
            continue
        signature = tuple(
            sorted(
                (field, value)
                for field, value in formatting.items()
                if field
                in {
                    "fontFamilyEastAsia",
                    "fontSizePt",
                    "alignment",
                    "firstLineIndentCm",
                    "lineSpacing",
                    "spaceBeforePt",
                    "spaceAfterPt",
                }
            )
        )
        if signature:
            clusters.setdefault(signature, []).append(block)

    rules: list[FormatRule] = []
    for cluster_blocks in clusters.values():
        if len(cluster_blocks) < 2:
            continue
        formatting = cluster_blocks[0].context.get("formatting")
        if not isinstance(formatting, dict):
            continue
        chunk = RequirementChunk(
            text="；".join(block.text for block in cluster_blocks[:3]),
            location=",".join(block.location for block in cluster_blocks[:3]),
            target_hint="body.paragraph",
            evidence_type="style_cluster",
        )
        font_expectation = {
            field: formatting[field]
            for field in ["fontFamilyEastAsia", "fontSizePt"]
            if field in formatting
        }
        if font_expectation:
            rules.append(
                _rule(
                    "body_font",
                    RuleCategory.font,
                    "body.paragraph",
                    None,
                    font_expectation,
                    chunk,
                    source_type,
                    Severity.major,
                    confidence=0.82,
                )
            )
        paragraph_expectation = {
            field: formatting[field]
            for field in ["alignment", "firstLineIndentCm", "lineSpacing"]
            if field in formatting
        }
        if paragraph_expectation:
            rules.append(
                _rule(
                    "body_paragraph_from_style_cluster",
                    RuleCategory.paragraph,
                    "body.paragraph",
                    None,
                    paragraph_expectation,
                    chunk,
                    source_type,
                    Severity.major,
                    tolerance={"firstLineIndentCm": 0.15},
                    confidence=0.82,
                )
            )
    return rules


def _extract_exemplar_rules(
    blocks: list[RequirementBlock],
    source_type: SourceType,
) -> list[FormatRule]:
    rules: list[FormatRule] = []
    for block in blocks:
        if block.type != "paragraph" or _looks_like_toc_entry(block.text):
            continue
        level = _heading_exemplar_level(block.text)
        if level is None:
            continue
        formatting = block.context.get("formatting")
        if not isinstance(formatting, dict):
            continue
        chunk = RequirementChunk(text=block.text, location=block.location)
        scope = f"heading.{level}"
        selector = f"Heading {level}"
        heading_expectation = _heading_expectation_from_formatting(formatting)
        if heading_expectation:
            rules.append(
                _rule(
                    f"heading{level}_font",
                    RuleCategory.heading,
                    scope,
                    selector,
                    heading_expectation,
                    chunk,
                    source_type,
                    Severity.major,
                    confidence=0.98,
                )
            )
        paragraph_expectation = _paragraph_expectation_from_formatting(formatting)
        if "firstLineIndentCm" in paragraph_expectation:
            rules.append(
                _rule(
                    f"heading_{level}_first_line_indent",
                    RuleCategory.paragraph,
                    scope,
                    selector,
                    {"firstLineIndentCm": paragraph_expectation["firstLineIndentCm"]},
                    chunk,
                    source_type,
                    Severity.major,
                    confidence=0.98,
                )
            )
        if "alignment" in paragraph_expectation:
            rules.append(
                _rule(
                    f"heading_{level}_alignment",
                    RuleCategory.paragraph,
                    scope,
                    selector,
                    {"alignment": paragraph_expectation["alignment"]},
                    chunk,
                    source_type,
                    Severity.minor,
                    confidence=0.98,
                )
            )
        spacing = {
            field: paragraph_expectation[field]
            for field in ["spaceBeforePt", "spaceAfterPt"]
            if field in paragraph_expectation
        }
        if spacing:
            rules.append(
                _rule(
                    f"heading_{level}_paragraph_spacing",
                    RuleCategory.paragraph,
                    scope,
                    selector,
                    spacing,
                    chunk,
                    source_type,
                    Severity.minor,
                    confidence=0.98,
                )
            )
    return rules


def _heading_exemplar_level(text: str) -> int | None:
    match = re.match(r"^\s*(\d+(?:\.\d+){0,5})\s+\S+", text)
    if not match:
        return None
    return min(match.group(1).count(".") + 1, 6)


def _looks_like_toc_entry(text: str) -> bool:
    return bool(re.match(r"^\s*\d+(?:\.\d+){0,5}\s+.+\s+\d+\s*$", text))


def _heading_expectation_from_formatting(formatting: dict[str, object]) -> dict[str, object]:
    expectation: dict[str, object] = {}
    for field in ["fontFamilyEastAsia", "fontSizePt", "bold", "alignment"]:
        if field in formatting:
            expectation[field] = formatting[field]
    return expectation


def _paragraph_expectation_from_formatting(formatting: dict[str, object]) -> dict[str, object]:
    expectation: dict[str, object] = {}
    expectation["firstLineIndentCm"] = formatting.get("firstLineIndentCm", 0.0)
    expectation["spaceBeforePt"] = formatting.get("spaceBeforePt", 0.0)
    expectation["spaceAfterPt"] = formatting.get("spaceAfterPt", 0.0)
    expectation["alignment"] = formatting.get("alignment", "left")
    return expectation


def _local_rule_candidates(chunks: list[RequirementChunk]) -> list[ExtractedRuleCandidate]:
    candidates: list[ExtractedRuleCandidate] = []
    candidates.extend(_structure_candidates(chunks))
    candidates.extend(_toc_candidates(chunks))
    candidates.extend(_caption_candidates(chunks))
    candidates.extend(_reference_candidates(chunks))
    return candidates


def _structure_candidates(chunks: list[RequirementChunk]) -> list[ExtractedRuleCandidate]:
    section_names = [
        "封面",
        "诚信声明",
        "版权声明",
        "中文摘要",
        "中文关键词",
        "英文摘要",
        "英文关键词",
        "目录",
        "正文",
        "致谢",
        "参考文献",
    ]
    matched: list[str] = []
    evidence: list[str] = []
    locations: list[str] = []
    for chunk in chunks:
        for name in section_names:
            if name in chunk.text and name not in matched:
                matched.append(name)
                evidence.append(chunk.text)
                if chunk.location:
                    locations.append(chunk.location)
    if len(matched) < 2:
        return []
    ordered = [name for name in section_names if name in matched]
    return [
        ExtractedRuleCandidate(
            category=RuleCategory.structure,
            target_scope="document.structure",
            selector="论文结构",
            expectation={"requiredSections": ordered},
            evidence_span="；".join(evidence[:4]),
            location=",".join(locations[:4]) if locations else None,
            checkability="checkable",
            confidence=0.82,
        )
    ]


def _toc_candidates(chunks: list[RequirementChunk]) -> list[ExtractedRuleCandidate]:
    for chunk in chunks:
        if "目录" in chunk.text or "目次" in chunk.text:
            return [
                ExtractedRuleCandidate(
                    category=RuleCategory.toc,
                    target_scope="document.toc",
                    selector="目录",
                    expectation={"requiresToc": True, "requiresEntries": True},
                    evidence_span=chunk.text,
                    location=chunk.location,
                    checkability="checkable",
                    confidence=0.84,
                )
            ]
    return []


def _caption_candidates(chunks: list[RequirementChunk]) -> list[ExtractedRuleCandidate]:
    for chunk in chunks:
        if any(keyword in chunk.text for keyword in ["图题", "表题", "题注", "图注", "表注"]):
            return [
                ExtractedRuleCandidate(
                    category=RuleCategory.caption,
                    target_scope="document.caption",
                    selector="图题和表题",
                    expectation={"captionPattern": "图1.1 题名 / 表1.1 题名"},
                    evidence_span=chunk.text,
                    location=chunk.location,
                    checkability="checkable",
                    confidence=0.8,
                )
            ]
    return []


def _reference_candidates(chunks: list[RequirementChunk]) -> list[ExtractedRuleCandidate]:
    for chunk in chunks:
        if _is_reference_requirement(chunk.text):
            return [
                ExtractedRuleCandidate(
                    category=RuleCategory.reference,
                    target_scope="document.references",
                    selector="参考文献",
                    expectation={"requiresReferences": True, "numbering": "bracketed"},
                    evidence_span=chunk.text,
                    location=chunk.location,
                    checkability="checkable",
                    confidence=0.82,
                )
            ]
    return []


def _llm_rule_candidates(
    blocks: list[RequirementBlock],
) -> tuple[list[ExtractedRuleCandidate], list[RuleExtractionIssue]]:
    settings = get_settings()
    if not settings.llm_api_base or not settings.llm_api_key or not settings.llm_model:
        raise RuleExtractionConfigurationError(
            "DOC_CHECKER_RULE_EXTRACTOR_MODE=hybrid 时必须配置 "
            "DOC_CHECKER_LLM_API_BASE、DOC_CHECKER_LLM_API_KEY、DOC_CHECKER_LLM_MODEL。"
        )

    payload = {
        "model": settings.llm_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是论文格式规范抽取器。只从用户提供的规范块中抽取规则候选，"
                    "必须只返回 JSON 对象：{\"rule_candidates\": [...]}。"
                    "每条候选只能包含 category、target_scope、selector、expectation、"
                    "evidence_span、location、checkability、confidence、reason 字段。"
                    "category 只能是 page、font、paragraph、heading、header_footer、"
                    "caption、reference、structure、toc 之一，禁止自造类别。"
                    "checkability 只能是 checkable、needs_confirmation、unsupported 之一，"
                    "禁止使用 specific、vague 等其他值。"
                    "expectation 必须是 JSON object，不能是字符串；无法结构化时返回空对象。"
                    "evidence_span 必须逐字摘自用户提供的规范块，不得编造来源。"
                    "示例：{\"rule_candidates\":[{\"category\":\"structure\","
                    "\"target_scope\":\"abstract\",\"selector\":\"中文摘要\","
                    "\"expectation\":{\"approxWordCount\":300},"
                    "\"evidence_span\":\"中文摘要要求300字左右。\","
                    "\"location\":\"paragraph:42\","
                    "\"checkability\":\"needs_confirmation\","
                    "\"confidence\":0.8,"
                    "\"reason\":\"字数约束需要人工确认\"}]}"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    [block.model_dump() for block in blocks[:80]],
                    ensure_ascii=False,
                ),
            },
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        settings.llm_api_base.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return [], [
            RuleExtractionIssue(
                reason_code="invalid_llm_response",
                message=f"LLM 规则抽取调用失败：{exc}",
            )
        ]

    content = response_payload["choices"][0]["message"]["content"]
    try:
        parsed = json.loads(content)
        candidates = TypeAdapter(list[ExtractedRuleCandidate]).validate_python(
            parsed.get("rule_candidates", [])
        )
    except (KeyError, TypeError, json.JSONDecodeError, ValidationError):
        return [], [
            RuleExtractionIssue(
                reason_code="invalid_llm_response",
                message=(
                    "LLM 返回的规则候选格式不符合系统 schema，"
                    "已拒绝本次 LLM 候选；本地规则抽取结果仍可使用。"
                ),
                excerpt=str(content)[:300],
            )
        ]
    issues = [
        RuleExtractionIssue(
            location=candidate.location,
            category=candidate.category,
            reason_code="ambiguous_requirement",
            message="LLM 候选缺少原文证据，已拒绝映射为规则。",
            excerpt=str(candidate.model_dump())[:300],
        )
        for candidate in candidates
        if not candidate.evidence_span.strip()
    ]
    valid_candidates = [candidate for candidate in candidates if candidate.evidence_span.strip()]
    return valid_candidates, issues


def _blocks_from_chunks(chunks: list[RequirementChunk]) -> list[RequirementBlock]:
    return [
        RequirementBlock(
            id=chunk.location or f"chunk:{index}",
            type="paragraph",
            location=chunk.location or f"chunk:{index}",
            text=chunk.text,
        )
        for index, chunk in enumerate(chunks, start=1)
    ]


def _block_target_hint(block: RequirementBlock) -> str | None:
    if block.type == "comment":
        nearby_text = str(block.context.get("nearby_text", ""))
        combined = f"{nearby_text} {block.text}"
        return _target_hint_from_text(combined)
    return _target_hint_from_text(block.text)


def _block_evidence_type(block: RequirementBlock) -> str:
    if block.type == "comment":
        return "comment_anchor" if block.context.get("nearby_location") else "explicit_text"
    if block.type == "table":
        return "table_cell"
    if block.type in {"header", "footer"}:
        return "explicit_text"
    if _heading_exemplar_level(block.text) is not None or _target_hint_from_text(block.text):
        return "exemplar_format"
    return "explicit_text"


def _target_hint_from_text(text: str) -> str | None:
    if "正文段落" in text or re.search(r"(^|[（(])正文([）)]|$)", text):
        return "body.paragraph"
    if not _has_explicit_non_body_target(text) and _looks_like_body_format_requirement(text):
        return "body.paragraph"
    return None


def _looks_like_body_format_requirement(text: str) -> bool:
    return (
        ("中文" in text or "宋体" in text)
        and ("英文" in text or "数字" in text or "Times New Roman" in text)
        and "首行缩进" in text
        and "行距" in text
    )


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


def _has_explicit_non_body_target(text: str) -> bool:
    return any(
        keyword in text
        for keyword in [
            "摘要",
            "关键词",
            "一级标题",
            "二级标题",
            "三级标题",
            "目录",
            "图题",
            "图注",
            "表题",
            "表注",
            "参考文献",
        ]
    )


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


def _has_non_body_format_context(text: str) -> bool:
    return any(
        keyword in text
        for keyword in [
            "图题",
            "图注",
            "表题",
            "表注",
            "题注",
            "图中",
            "表中",
            "公式",
            "表达式",
            "目录",
            "参考文献",
        ]
    )


def _is_reference_requirement(text: str) -> bool:
    if re.search(r"(不|避免|禁止|无需|不得).{0,8}(引用|参考文献)", text):
        return False
    return bool(
        "参考文献" in text
        and re.search(r"(著录|编排|格式|编号|顺序|GB/T|列出|不少于)", text, re.I)
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
        source=RuleSource(
            type=source_type,
            excerpt=chunk.text[:300],
            location=chunk.location,
            evidence_type=chunk.evidence_type,
        ),
        confidence=confidence,
        enabled=True,
    )


def _split_rules_by_confirmation(
    rules: list[FormatRule],
) -> tuple[list[FormatRule], list[FormatRule]]:
    auto_rules: list[FormatRule] = []
    suggested_rules: list[FormatRule] = []
    for rule in rules:
        if rule.confidence >= 0.8 and rule.capability_status == "auto_checkable":
            auto_rules.append(rule)
            continue
        suggested_rules.append(
            rule.model_copy(
                update={
                    "enabled": False,
                    "capability_status": "needs_confirmation",
                    "confirmation_required": True,
                }
            )
        )
    return auto_rules, suggested_rules


def _move_conflicting_rules_to_confirmation(
    rules: list[FormatRule],
) -> tuple[list[FormatRule], list[RuleExtractionIssue]]:
    by_field: dict[tuple[str, str | None, RuleCategory, str], list[tuple[FormatRule, object]]] = {}
    conflict_keys: set[tuple[str, str | None, RuleCategory, str]] = set()
    auto_allowed: set[tuple[int, str, str | None, RuleCategory, str]] = set()
    issues: list[RuleExtractionIssue] = []
    for rule in rules:
        for field, value in rule.expectation.items():
            key = (rule.target.scope, rule.target.selector, rule.category, field)
            by_field.setdefault(key, []).append((rule, value))

    for key, values in by_field.items():
        distinct_values = []
        for _, value in values:
            if value not in distinct_values:
                distinct_values.append(value)
        if len(distinct_values) <= 1:
            continue
        conflict_keys.add(key)
        ranked = sorted(
            values,
            key=lambda item: _rule_conflict_rank(item[0]),
            reverse=True,
        )
        top_rank = _rule_conflict_rank(ranked[0][0])
        top_rules = [item for item in ranked if _rule_conflict_rank(item[0]) == top_rank]
        if len(top_rules) == 1:
            winner = top_rules[0][0]
            auto_allowed.add((id(winner), *key))
            message = (
                f"同一检查目标存在冲突规则：{key[3]} 存在多个值，"
                "已优先保留高置信/高优先级证据，其余规则需要人工确认。"
            )
            location = winner.source.location
            excerpt = winner.source.excerpt
        else:
            winner = ranked[0][0]
            message = (
                f"同一检查目标存在冲突规则：{key[3]} 存在多个同优先级值，"
                "需要人工确认。"
            )
            location = winner.source.location
            excerpt = winner.source.excerpt
        issues.append(
            RuleExtractionIssue(
                location=location,
                category=winner.category,
                reason_code="ambiguous_requirement",
                message=message,
                excerpt=excerpt,
            )
        )

    normalized_rules: list[FormatRule] = []
    for rule in rules:
        conflicting_fields = [
            field
            for field in rule.expectation
            if (rule.target.scope, rule.target.selector, rule.category, field) in conflict_keys
        ]
        rule_conflicts = bool(conflicting_fields)
        if not rule_conflicts:
            normalized_rules.append(rule)
            continue
        if all(
            (
                id(rule),
                rule.target.scope,
                rule.target.selector,
                rule.category,
                field,
            )
            in auto_allowed
            for field in conflicting_fields
        ):
            normalized_rules.append(rule)
            continue
        normalized_rules.append(
            rule.model_copy(
                update={
                    "enabled": False,
                    "capability_status": "needs_confirmation",
                    "confirmation_required": True,
                }
            )
        )
    return normalized_rules, issues


def _rule_conflict_rank(rule: FormatRule) -> tuple[int, float]:
    evidence_rank = {
        "template": 6,
        "exemplar_format": 5,
        "comment_anchor": 4,
        "style_cluster": 3,
        "table_cell": 2,
        "explicit_text": 1,
        "manual_text": 1,
        "llm_candidate": 1,
    }.get(rule.source.evidence_type, 0)
    return (evidence_rank, rule.confidence)


def _conflict_issues(rules: list[FormatRule]) -> list[RuleExtractionIssue]:
    by_field: dict[tuple[str, str | None, RuleCategory, str], FormatRule] = {}
    reported: set[tuple[str, str | None, RuleCategory, str]] = set()
    issues: list[RuleExtractionIssue] = []
    for rule in rules:
        for field, value in rule.expectation.items():
            key = (rule.target.scope, rule.target.selector, rule.category, field)
            existing = by_field.get(key)
            if existing is None:
                by_field[key] = rule
                continue
            existing_value = existing.expectation.get(field)
            if existing_value == value:
                continue
            if key in reported:
                continue
            reported.add(key)
            issues.append(
                RuleExtractionIssue(
                    location=rule.source.location,
                    category=rule.category,
                    reason_code="ambiguous_requirement",
                    message=(
                        f"同一检查目标存在冲突规则：{field} 同时为 "
                        f"{existing_value} 和 {value}，需要人工确认。"
                    ),
                    excerpt=rule.source.excerpt,
                )
            )
    return issues


def _extract_unsupported_requirements(
    chunks: list[RequirementChunk],
    rules: list[FormatRule],
    issues: list[RuleExtractionIssue] | None = None,
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
                        reason_code="missing_checker",
                        target_scope=None,
                        capability_status="unsupported",
                    )
                )
                break
    for issue in issues or []:
        if (
            issue.reason_code not in {"unsupported_field", "ambiguous_requirement"}
            and _issue_covered_by_rule(issue, rules)
        ):
            continue
        unsupported.append(
            UnsupportedRequirement(
                category=issue.category or RuleCategory.structure,
                excerpt=issue.excerpt or issue.message,
                location=issue.location,
                reason=issue.message,
                reason_code=issue.reason_code,
                target_scope=None,
                capability_status=(
                    "conflict"
                    if "冲突" in issue.message
                    else "needs_confirmation"
                    if issue.reason_code == "ambiguous_requirement"
                    else "unsupported"
                ),
            )
        )
    return _dedupe_unsupported(unsupported)


def _issue_covered_by_rule(
    issue: RuleExtractionIssue,
    rules: list[FormatRule],
) -> bool:
    if issue.category is None or issue.excerpt is None:
        return False
    return any(
        rule.category == issue.category and rule.source.excerpt == issue.excerpt[:300]
        for rule in rules
    )


def _has_checkable_page_header_footer(chunk: RequirementChunk) -> bool:
    return bool(re.search(r"(页眉|页脚)\s*[0-9]+(?:\.[0-9]+)?\s*cm", chunk.text, re.I))


def _build_warnings(
    chunks: list[RequirementChunk],
    rules: list[FormatRule],
    suggested_rules: list[FormatRule],
    unsupported: list[UnsupportedRequirement],
) -> list[str]:
    warnings: list[str] = []
    if not rules:
        warnings.append("未识别到可自动校验的格式规则，请补充字体、字号、行距、缩进或页边距要求。")
    for item in unsupported:
        location = f"{item.location}：" if item.location else ""
        warnings.append(f"{location}{item.reason}")
    if suggested_rules:
        warnings.append(f"有 {len(suggested_rules)} 条规则需要人工确认后才会参与自动检查。")
    if not rules and not unsupported and chunks:
        warnings.append("规范文本已读取，但未命中当前规则能力矩阵中的格式要求。")
    return warnings


def _summary(
    rules: list[FormatRule],
    unsupported: list[UnsupportedRequirement],
    chunks: list[RequirementChunk] | None = None,
    *,
    suggested_rules: list[FormatRule] | None = None,
    issues: list[RuleExtractionIssue] | None = None,
) -> ExtractionSummary:
    suggested_rules = suggested_rules or []
    issues = issues or []
    supported_categories = sorted({rule.category for rule in rules}, key=lambda item: item.value)
    unsupported_categories = sorted(
        {item.category for item in unsupported},
        key=lambda item: item.value,
    )
    present_categories = set(supported_categories) | set(unsupported_categories)
    uncovered = sorted(set(ALL_RULE_CATEGORIES) - present_categories, key=lambda item: item.value)
    total_requirements = _count_requirement_candidates(
        chunks or [],
        rules + suggested_rules,
        unsupported,
    )
    handled = len(rules) + len(suggested_rules) + len(unsupported)
    return ExtractionSummary(
        total_requirements=total_requirements,
        structured_rules=len(rules),
        unsupported_requirements=len(unsupported),
        low_confidence_rules=len(suggested_rules),
        supported_categories=supported_categories,
        unsupported_categories=unsupported_categories,
        uncovered_categories=uncovered,
        auto_checkable_rules=len(rules),
        needs_confirmation_rules=len(suggested_rules),
        conflict_requirements=len([issue for issue in issues if "冲突" in issue.message]),
        coverage_rate=round(handled / total_requirements, 3) if total_requirements else 0,
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
            chunks.append(
                RequirementChunk(
                    text=part,
                    location=part_location,
                    evidence_type="manual_text",
                )
            )
    if not chunks:
        normalized = re.sub(r"\s+", " ", text.strip())
        chunks.extend(
            RequirementChunk(text=part.strip(), evidence_type="manual_text")
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
    by_id: dict[str, FormatRule] = {}
    order: list[str] = []
    for rule in rules:
        existing = by_id.get(rule.id)
        if existing is None:
            by_id[rule.id] = rule
            order.append(rule.id)
            continue
        by_id[rule.id] = _merge_rule(existing, rule)
    return [by_id[rule_id] for rule_id in order]


def _merge_rule(existing: FormatRule, incoming: FormatRule) -> FormatRule:
    expectation = dict(existing.expectation)
    for field, value in incoming.expectation.items():
        if field not in expectation or incoming.confidence > existing.confidence:
            expectation[field] = value
    confidence = max(existing.confidence, incoming.confidence)
    source = incoming.source if incoming.confidence > existing.confidence else existing.source
    return existing.model_copy(
        update={
            "expectation": expectation,
            "confidence": confidence,
            "source": source,
        }
    )


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
