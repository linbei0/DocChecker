from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ParseWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    location: str | None = None


class SectionNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int
    page_width_cm: float | None = None
    page_height_cm: float | None = None
    margin_top_cm: float | None = None
    margin_bottom_cm: float | None = None
    margin_left_cm: float | None = None
    margin_right_cm: float | None = None
    header_distance_cm: float | None = None
    footer_distance_cm: float | None = None


class ParagraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int
    text: str
    style_name: str | None = None
    section_index: int = 0
    font_family: str | None = None
    font_family_east_asia: str | None = None
    font_family_ascii: str | None = None
    font_size_pt: float | None = None
    bold: bool | None = None
    alignment: str | None = None
    first_line_indent_cm: float | None = None
    line_spacing: float | None = None
    space_before_pt: float | None = None
    space_after_pt: float | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class DocumentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    source_filename: str
    package_parts: list[str]
    sections: list[SectionNode]
    paragraphs: list[ParagraphNode]
    table_count: int
    image_count: int
    styles: dict[str, dict[str, Any]]
    parse_warnings: list[ParseWarning] = Field(default_factory=list)
