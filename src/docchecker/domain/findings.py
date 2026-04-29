from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from docchecker.domain.enums import Certainty, RuleCategory, Severity


class FindingLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_path: str | None = None
    display_path: str | None = None
    paragraph_number: int | None = None
    section_name: str | None = None
    paragraph_index: int | None = None
    table_index: int | None = None
    row_index: int | None = None
    column_index: int | None = None
    area: str | None = None
    xml_path: str | None = None


class CheckFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    rule_id: str
    checker_id: str
    category: RuleCategory | None = None
    severity: Severity
    location: FindingLocation
    expected: dict[str, Any]
    actual: dict[str, Any]
    excerpt: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    evidence: str
    suggestion: str
    certainty: Certainty = Certainty.certain
    status: Literal["missing_actual", "mixed_value", "unsupported_field", "mismatch"] = (
        "mismatch"
    )


class CheckReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    document_id: str
    ruleset_id: str
    checker_version: str
    generated_at: str
    findings: list[CheckFinding]
    parse_warnings: list[str] = Field(default_factory=list)
