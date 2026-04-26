from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from docchecker.domain.enums import RuleCategory, Severity, SourceType


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


class RuleSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    source_type: SourceType
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    locale: str = "zh-CN"
    rules: list[FormatRule] = Field(default_factory=list)
    created_at: str
