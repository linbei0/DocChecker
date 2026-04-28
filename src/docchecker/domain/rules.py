from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from docchecker.domain.enums import DraftRuleSetStatus, RuleCategory, Severity, SourceType


class RuleTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: str = Field(min_length=1)
    selector: str | None = None


class RuleSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: SourceType
    excerpt: str
    location: str | None = None


class FormatRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    category: RuleCategory
    target: RuleTarget
    expectation: dict[str, Any]
    tolerance: dict[str, Any] = Field(default_factory=dict)
    severity: Severity
    source: RuleSource
    confidence: float = Field(ge=0, le=1, default=1)
    enabled: bool = True


class ExtractionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_requirements: int = 0
    structured_rules: int = 0
    unsupported_requirements: int = 0
    low_confidence_rules: int = 0
    supported_categories: list[RuleCategory] = Field(default_factory=list)
    unsupported_categories: list[RuleCategory] = Field(default_factory=list)
    uncovered_categories: list[RuleCategory] = Field(default_factory=list)


RuleExtractionReasonCode = Literal[
    "missing_checker",
    "ambiguous_requirement",
    "out_of_scope",
    "llm_not_configured",
    "invalid_llm_response",
]


class UnsupportedRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: RuleCategory
    excerpt: str
    location: str | None = None
    reason: str
    reason_code: RuleExtractionReasonCode = "missing_checker"


class ExtractedRuleCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: RuleCategory
    target_scope: str
    selector: str | None = None
    expectation: dict[str, Any] = Field(default_factory=dict)
    evidence_span: str
    location: str | None = None
    checkability: Literal["checkable", "needs_confirmation", "unsupported"]
    confidence: float = Field(ge=0, le=1, default=0.8)
    reason: str | None = None


class RuleExtractionIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: str | None = None
    category: RuleCategory | None = None
    reason_code: RuleExtractionReasonCode
    message: str
    excerpt: str | None = None


class RuleExtractionTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str
    candidates: list[ExtractedRuleCandidate] = Field(default_factory=list)
    issues: list[RuleExtractionIssue] = Field(default_factory=list)


class RuleSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    source_type: SourceType
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    locale: str = "zh-CN"
    rules: list[FormatRule] = Field(default_factory=list)
    created_at: str


class DraftRuleSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    document_id: str
    source_type: SourceType
    version: str = "1.0.0"
    locale: str = "zh-CN"
    rules: list[FormatRule] = Field(default_factory=list)
    parse_warnings: list[str] = Field(default_factory=list)
    extraction_summary: ExtractionSummary = Field(default_factory=ExtractionSummary)
    unsupported_requirements: list[UnsupportedRequirement] = Field(default_factory=list)
    extraction_trace: RuleExtractionTrace | None = None
    status: DraftRuleSetStatus = DraftRuleSetStatus.draft
    published_ruleset_id: str | None = None
    created_at: str
    updated_at: str
