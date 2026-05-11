from docchecker.domain.enums import RuleCategory, Severity, SourceType
from docchecker.domain.rules import FormatRule, RuleSource, RuleTarget
from docchecker.services.rule_extractor_types import RequirementChunk


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


