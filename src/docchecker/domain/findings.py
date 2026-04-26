from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from docchecker.domain.enums import Certainty, Severity


class FindingLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_path: str | None = None
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
    severity: Severity
    location: FindingLocation
    expected: dict[str, Any]
    actual: dict[str, Any]
    evidence: str
    suggestion: str
    certainty: Certainty = Certainty.certain


class CheckReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    document_id: str
    ruleset_id: str
    checker_version: str
    generated_at: str
    findings: list[CheckFinding]
    parse_warnings: list[str] = Field(default_factory=list)
