from dataclasses import dataclass

from docchecker.domain.rules import (
    ExtractionSummary,
    FormatRule,
    RuleExtractionTrace,
    UnsupportedRequirement,
)


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


