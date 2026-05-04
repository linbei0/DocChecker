from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ParseWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    location: str | None = None


class RunSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    script: str
    font_family: str | None = None
    font_family_east_asia: str | None = None
    font_family_ascii: str | None = None
    font_size_pt: float | None = None
    bold: bool | None = None
    style_name: str | None = None
    source: str | None = None


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


class LogicalSectionNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str
    title: str
    start_paragraph_index: int
    end_paragraph_index: int | None = None


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
    runs: list[RunSpan] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class HeaderFooterFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_index: int
    kind: str
    text: str
    inherited: bool = False
    paragraph_count: int = 0
    paragraphs: list["HeaderFooterParagraphFact"] = Field(default_factory=list)


class HeaderFooterParagraphFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_index: int
    kind: str
    index: int
    text: str
    style_name: str | None = None
    effective_format: dict[str, Any] = Field(default_factory=dict)
    effective_format_sources: dict[str, str | None] = Field(default_factory=dict)


class TableCellFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_index: int
    column_index: int
    text: str


class TableFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int
    row_count: int
    column_count: int
    cells: list[TableCellFact] = Field(default_factory=list)
    caption_text: str | None = None
    caption_position: str | None = None
    preceding_paragraph_index: int | None = None
    following_paragraph_index: int | None = None


class NumberingFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paragraph_index: int
    num_id: str | None = None
    level: str | None = None
    style_name: str | None = None
    text: str


class FieldFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paragraph_index: int | None = None
    part_name: str = "word/document.xml"
    field_type: str
    instruction: str
    text: str | None = None


class StyleFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    style_id: str | None = None
    type: str | None = None
    base_style: str | None = None
    formatting: dict[str, Any] = Field(default_factory=dict)


class EffectiveFormatFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_type: str
    owner_id: str
    paragraph_index: int | None = None
    section_index: int | None = None
    style_name: str | None = None
    values: dict[str, Any] = Field(default_factory=dict)
    sources: dict[str, str | None] = Field(default_factory=dict)


class DocumentFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    xml_parts: dict[str, str] = Field(default_factory=dict)
    headers_footers: list[HeaderFooterFact] = Field(default_factory=list)
    tables: list[TableFact] = Field(default_factory=list)
    numbering: list[NumberingFact] = Field(default_factory=list)
    fields: list[FieldFact] = Field(default_factory=list)
    styles: list[StyleFact] = Field(default_factory=list)
    effective_formats: list[EffectiveFormatFact] = Field(default_factory=list)


class DocumentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    source_filename: str
    package_parts: list[str]
    sections: list[SectionNode]
    logical_sections: list[LogicalSectionNode] = Field(default_factory=list)
    paragraphs: list[ParagraphNode]
    table_count: int
    image_count: int
    styles: dict[str, dict[str, Any]]
    facts: DocumentFacts = Field(default_factory=DocumentFacts)
    parse_warnings: list[ParseWarning] = Field(default_factory=list)


class UploadedDocumentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    filename: str
    path: str
    original_path: str
    original_format: str
    normalized_format: str
    size_bytes: int
