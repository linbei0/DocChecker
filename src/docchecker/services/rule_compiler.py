import re
from dataclasses import dataclass, field

from docchecker.checkers.capabilities import (
    supported_expectation,
    unsupported_expectation_fields,
)
from docchecker.domain.enums import RuleCategory, Severity, SourceType
from docchecker.domain.rules import (
    ExtractedRuleCandidate,
    FormatRule,
    RuleExtractionIssue,
    RuleSource,
    RuleTarget,
)

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
    issues: list[RuleExtractionIssue] = field(default_factory=list)


def compile_rule_candidates(
    candidates: list[ExtractedRuleCandidate],
    *,
    source_type: SourceType,
) -> RuleCompilationResult:
    result = RuleCompilationResult()
    for candidate in candidates:
        if candidate.checkability != "checkable":
            result.issues.append(
                RuleExtractionIssue(
                    location=candidate.location,
                    category=candidate.category,
                    reason_code=(
                        "ambiguous_requirement"
                        if candidate.checkability == "needs_confirmation"
                        else "missing_checker"
                    ),
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
        expectation = supported_expectation(
            candidate.category,
            candidate.target_scope,
            normalized_expectation,
        )
        unsupported_fields = unsupported_expectation_fields(
            candidate.category,
            candidate.target_scope,
            normalized_expectation,
        )
        if unsupported_fields:
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

        result.rules.append(
            FormatRule(
                id=_candidate_rule_id(candidate),
                category=candidate.category,
                target=RuleTarget(
                    scope=candidate.target_scope,
                    selector=candidate.selector,
                ),
                expectation=expectation,
                severity=_candidate_severity(candidate.category),
                source=RuleSource(
                    type=source_type,
                    excerpt=candidate.evidence_span[:300],
                    location=candidate.location,
                ),
                confidence=candidate.confidence,
                enabled=True,
            )
        )
    return result


def _candidate_rule_id(candidate: ExtractedRuleCandidate) -> str:
    return {
        RuleCategory.structure: "structure_required_sections",
        RuleCategory.toc: "toc_basic_shape",
        RuleCategory.caption: "caption_basic_pattern",
        RuleCategory.reference: "reference_basic_entries",
    }.get(candidate.category, f"{candidate.category.value}_candidate")


def _candidate_severity(category: RuleCategory) -> Severity:
    return Severity.major if category == RuleCategory.structure else Severity.minor


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
    if category == RuleCategory.toc:
        if "autoGenerated" in normalized and "requiresToc" not in normalized:
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
