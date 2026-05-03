from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

RequirementBlockType = Literal["paragraph", "table", "comment", "header", "footer"]


class RequirementBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: RequirementBlockType
    location: str
    text: str
    style_name: str | None = None
    heading_path: list[str] = Field(default_factory=list)
    table_index: int | None = None
    row_index: int | None = None
    column_count: int | None = None
    cells: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)


class RequirementDocumentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_filename: str
    blocks: list[RequirementBlock]
    markdown: str
    parse_warnings: list[str] = Field(default_factory=list)


class RequirementDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    filename: str
    path: str
    size_bytes: int
    extracted_text: str
    blocks: list[RequirementBlock] = Field(default_factory=list)
    original_format: str
    normalized_format: str
    created_at: str
