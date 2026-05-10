import re
from dataclasses import dataclass, field

from docchecker.checkers.capabilities import (
    supported_expectation,
    supports_scope,
    unsupported_expectation_fields,
)
from docchecker.checkers.rule_dsl import (
    execution_expectation,
    has_execution_assertions,
    non_execution_expectation,
)
from docchecker.domain.enums import RuleCategory, Severity, SourceType
from docchecker.domain.rules import (
    ExtractedRuleCandidate,
    FormatRule,
    RuleExtractionIssue,
    RuleSource,
    RuleTarget,
)

AUTO_CHECK_MIN_CONFIDENCE = 0.8
NEEDS_CONFIRMATION_MIN_CONFIDENCE = 0.6

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


@dataclass
class RuleCompilationResult:
    rules: list[FormatRule] = field(default_factory=list)
    suggested_rules: list[FormatRule] = field(default_factory=list)
    issues: list[RuleExtractionIssue] = field(default_factory=list)
    unsupported_field_count: int = 0
    auto_checkable_candidate_count: int = 0
    needs_confirmation_candidate_count: int = 0
    unsupported_candidate_count: int = 0


def compile_rule_candidates(
    candidates: list[ExtractedRuleCandidate],
    *,
    source_type: SourceType,
) -> RuleCompilationResult:
    result = RuleCompilationResult()
    for candidate in candidates:
        target_scope, selector = _normalized_target(candidate)
        if candidate.checkability == "unsupported":
            result.unsupported_candidate_count += 1
            result.issues.append(
                RuleExtractionIssue(
                    location=candidate.location,
                    category=candidate.category,
                    reason_code="missing_checker",
                    message=candidate.reason
                    or "规则候选需要人工确认或当前系统暂不支持自动校验。",
                    excerpt=candidate.evidence_span[:300],
                )
            )
            continue

        normalized_expectation = _normalize_expectation(
            candidate.category,
            candidate.expectation,
        )
        uses_execution_backend = has_execution_assertions(normalized_expectation)

        if not uses_execution_backend and not supports_scope(
            candidate.category,
            scope=target_scope,
        ):
            result.unsupported_candidate_count += 1
            result.issues.append(
                RuleExtractionIssue(
                    location=candidate.location,
                    category=candidate.category,
                    reason_code="unsupported_field",
                    message=(
                        "规则候选目标范围不在当前检查能力矩阵内："
                        f"{target_scope}"
                    ),
                    excerpt=candidate.evidence_span[:300],
                )
            )
            continue

        regular_expectation = non_execution_expectation(normalized_expectation)
        expectation = supported_expectation(
            candidate.category,
            target_scope,
            regular_expectation,
        )
        unsupported_fields = unsupported_expectation_fields(
            candidate.category,
            target_scope,
            regular_expectation,
        )
        if uses_execution_backend:
            expectation.update(execution_expectation(normalized_expectation))
        if unsupported_fields:
            result.unsupported_field_count += len(unsupported_fields)
            result.issues.append(
                RuleExtractionIssue(
                    location=candidate.location,
                    category=candidate.category,
                    reason_code="unsupported_field",
                    message=(
                        "规则候选包含当前检查器不支持的字段："
                        + "、".join(unsupported_fields)
                    ),
                    excerpt=candidate.evidence_span[:300],
                )
            )
        if not expectation:
            continue

        rule = FormatRule(
            id=_candidate_rule_id(candidate),
            category=candidate.category,
            target=RuleTarget(
                scope=target_scope,
                selector=selector,
            ),
            expectation=expectation,
            tolerance=_candidate_tolerance(expectation),
            severity=_candidate_severity(candidate.category),
            source=RuleSource(
                type=source_type,
                excerpt=candidate.evidence_span[:300],
                location=candidate.location,
                evidence_type=candidate.evidence_type,
            ),
            confidence=candidate.confidence,
            enabled=True,
        )
        needs_confirmation = _candidate_requires_confirmation(candidate, target_scope)
        if (
            candidate.checkability == "checkable"
            and candidate.confidence >= AUTO_CHECK_MIN_CONFIDENCE
            and not needs_confirmation
        ):
            result.auto_checkable_candidate_count += 1
            result.rules.append(rule)
        elif candidate.confidence >= NEEDS_CONFIRMATION_MIN_CONFIDENCE:
            result.needs_confirmation_candidate_count += 1
            result.suggested_rules.append(
                rule.model_copy(
                    update={
                        "enabled": False,
                        "capability_status": "needs_confirmation",
                        "confirmation_required": True,
                    }
                )
            )
            result.issues.append(
                RuleExtractionIssue(
                    location=candidate.location,
                    category=candidate.category,
                    reason_code="ambiguous_requirement",
                    message=(
                        candidate.reason
                        or _confirmation_reason(candidate)
                        or "规则候选置信度不足，需要人工确认后才能自动检查。"
                    ),
                    excerpt=candidate.evidence_span[:300],
                )
            )
        else:
            result.needs_confirmation_candidate_count += 1
            result.issues.append(
                RuleExtractionIssue(
                    location=candidate.location,
                    category=candidate.category,
                    reason_code="ambiguous_requirement",
                    message=(
                        candidate.reason
                        or "规则候选置信度过低，未进入自动检查；请人工核对原文要求。"
                    ),
                    excerpt=candidate.evidence_span[:300],
                )
            )
    return result


def _normalized_target(candidate: ExtractedRuleCandidate) -> tuple[str, str | None]:
    if candidate.category == RuleCategory.heading:
        explicit_level = _explicit_heading_level(candidate.target_scope)
        explicit_level = explicit_level or _explicit_heading_level(candidate.evidence_span)
        if explicit_level is not None:
            return f"heading.{explicit_level}", f"Heading {explicit_level}"
    if (
        candidate.category == RuleCategory.paragraph
        and candidate.target_scope.lower() in {"document", "paragraph"}
        and _is_body_paragraph_candidate(candidate)
    ):
        return "body.paragraph", None
    return candidate.target_scope, candidate.selector


def _candidate_requires_confirmation(
    candidate: ExtractedRuleCandidate,
    normalized_scope: str,
) -> bool:
    if candidate.category == RuleCategory.heading:
        original_scope = candidate.target_scope.lower()
        if original_scope in {"heading", "heading.paragraph"} and not re.search(
            r"heading[ .]?[1-6]",
            normalized_scope,
            flags=re.I,
        ):
            return True
    return (
        candidate.category == RuleCategory.paragraph
        and candidate.target_scope.lower() in {"document", "paragraph"}
        and normalized_scope == candidate.target_scope
    )


def _confirmation_reason(candidate: ExtractedRuleCandidate) -> str | None:
    if candidate.category == RuleCategory.heading:
        return "标题候选没有明确到一级、二级或三级标题，已移入人工确认，避免套用到所有标题。"
    if candidate.category == RuleCategory.paragraph:
        return "段落候选没有明确作用范围，已移入人工确认，避免套用到摘要、关键词等专门段落。"
    return None


def _candidate_tolerance(expectation: dict[str, object]) -> dict[str, object]:
    tolerance: dict[str, object] = {}
    if "firstLineIndentCm" in expectation:
        tolerance["firstLineIndentCm"] = 0.15
    if "lineSpacing" in expectation:
        tolerance["lineSpacing"] = 0.05
    return tolerance


def _explicit_heading_level(text: str | None) -> int | None:
    if not text:
        return None
    for label, level in {
        "一级标题": 1,
        "二级标题": 2,
        "三级标题": 3,
        "四级标题": 4,
        "五级标题": 5,
        "六级标题": 6,
    }.items():
        if label in text:
            return level
    if match := re.search(r"heading[ .]?([1-6])", text, flags=re.I):
        return int(match.group(1))
    return None


def _is_body_paragraph_candidate(candidate: ExtractedRuleCandidate) -> bool:
    text = f"{candidate.selector or ''} {candidate.evidence_span}"
    return any(label in text for label in ["正文段落", "正文", "body.paragraph"])


def _candidate_rule_id(candidate: ExtractedRuleCandidate) -> str:
    return {
        RuleCategory.structure: "structure_required_sections",
        RuleCategory.toc: "toc_basic_shape",
        RuleCategory.caption: "caption_basic_pattern",
        RuleCategory.reference: "reference_basic_entries",
        RuleCategory.header_footer: "header_footer_basic",
        RuleCategory.abstract: "abstract_basic_requirements",
    }.get(candidate.category, f"{candidate.category.value}_candidate")


def _candidate_severity(category: RuleCategory) -> Severity:
    if category in {RuleCategory.structure, RuleCategory.abstract}:
        return Severity.major
    return Severity.minor


def _normalize_expectation(
    category: RuleCategory,
    expectation: dict[str, object],
) -> dict[str, object]:
    normalized = dict(expectation)
    if category in {RuleCategory.font, RuleCategory.heading, RuleCategory.paragraph}:
        if "fontName" in normalized and "fontFamilyEastAsia" not in normalized:
            normalized["fontFamilyEastAsia"] = normalized.pop("fontName")
        if "fontSize" in normalized and "fontSizePt" not in normalized:
            normalized["fontSizePt"] = _font_size_pt(normalized.pop("fontSize"))
        if "firstLineIndent" in normalized and "firstLineIndentCm" not in normalized:
            normalized["firstLineIndentCm"] = _indent_cm(
                normalized.pop("firstLineIndent")
            )
    if category == RuleCategory.page:
        _rename_field(normalized, "topMargin", "margin_top_cm", transform=_cm_value)
        _rename_field(normalized, "marginTop", "margin_top_cm", transform=_cm_value)
        _rename_field(normalized, "bottomMargin", "margin_bottom_cm", transform=_cm_value)
        _rename_field(
            normalized, "marginBottom", "margin_bottom_cm", transform=_cm_value
        )
        _rename_field(normalized, "leftMargin", "margin_left_cm", transform=_cm_value)
        _rename_field(normalized, "marginLeft", "margin_left_cm", transform=_cm_value)
        _rename_field(normalized, "rightMargin", "margin_right_cm", transform=_cm_value)
        _rename_field(normalized, "marginRight", "margin_right_cm", transform=_cm_value)
    if (
        category == RuleCategory.toc
        and "autoGenerated" in normalized
        and "requiresToc" not in normalized
    ):
        normalized["requiresToc"] = bool(normalized.pop("autoGenerated"))
    return {field: value for field, value in normalized.items() if value is not None}


def _rename_field(
    values: dict[str, object],
    old: str,
    new: str,
    *,
    transform,
) -> None:
    if old not in values or new in values:
        return
    values[new] = transform(values.pop(old))


def _font_size_pt(value: object) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    if not isinstance(value, str):
        return None
    if value in FONT_SIZE_BY_NAME:
        return float(FONT_SIZE_BY_NAME[value])
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", value)
    return float(match.group(1)) if match else None


def _indent_cm(value: object) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    if not isinstance(value, str):
        return None
    char_match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*字符", value)
    if char_match:
        return round(float(char_match.group(1)) * 0.37, 3)
    return _cm_value(value)


def _cm_value(value: object) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    if not isinstance(value, str):
        return None
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*cm", value, flags=re.I)
    if match:
        return float(match.group(1))
    plain_number = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*", value)
    return float(plain_number.group(1)) if plain_number else None
