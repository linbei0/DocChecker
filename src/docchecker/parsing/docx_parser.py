from pathlib import Path
from zipfile import ZipFile

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

from docchecker.domain.document import DocumentModel, ParagraphNode, ParseWarning, SectionNode

EMU_PER_CM = 360000
PT_PER_TWIP = 1 / 20


def _emu_to_cm(value: int | None) -> float | None:
    if value is None:
        return None
    return round(value / EMU_PER_CM, 3)


def _alignment_name(value: WD_ALIGN_PARAGRAPH | None) -> str | None:
    if value is None:
        return None
    return str(value).split(".")[-1].lower()


def _font_size_pt(paragraph) -> float | None:
    sizes = [run.font.size.pt for run in paragraph.runs if run.font.size is not None]
    if not sizes:
        return None
    first = sizes[0]
    if all(size == first for size in sizes):
        return first
    return None


def _font_family(paragraph) -> str | None:
    names = [run.font.name for run in paragraph.runs if run.font.name]
    if not names:
        return None
    first = names[0]
    if all(name == first for name in names):
        return first
    return None


def _bold(paragraph) -> bool | None:
    values = [run.bold for run in paragraph.runs if run.bold is not None]
    if not values:
        return None
    first = values[0]
    if all(value == first for value in values):
        return bool(first)
    return None


def parse_docx(path: Path, *, document_id: str, source_filename: str) -> DocumentModel:
    package_parts: list[str]
    with ZipFile(path) as package:
        package_parts = package.namelist()
        image_count = len([name for name in package_parts if name.startswith("word/media/")])

    document = Document(path)
    warnings: list[ParseWarning] = []
    sections = [
        SectionNode(
            index=index,
            page_width_cm=_emu_to_cm(section.page_width),
            page_height_cm=_emu_to_cm(section.page_height),
            margin_top_cm=_emu_to_cm(section.top_margin),
            margin_bottom_cm=_emu_to_cm(section.bottom_margin),
            margin_left_cm=_emu_to_cm(section.left_margin),
            margin_right_cm=_emu_to_cm(section.right_margin),
            header_distance_cm=_emu_to_cm(section.header_distance),
            footer_distance_cm=_emu_to_cm(section.footer_distance),
        )
        for index, section in enumerate(document.sections)
    ]

    paragraphs: list[ParagraphNode] = []
    for index, paragraph in enumerate(document.paragraphs):
        fmt = paragraph.paragraph_format
        paragraphs.append(
            ParagraphNode(
                index=index,
                text=paragraph.text,
                style_name=paragraph.style.name if paragraph.style else None,
                font_family=_font_family(paragraph),
                font_size_pt=_font_size_pt(paragraph),
                bold=_bold(paragraph),
                alignment=_alignment_name(paragraph.alignment),
                first_line_indent_cm=_emu_to_cm(fmt.first_line_indent),
                line_spacing=fmt.line_spacing if isinstance(fmt.line_spacing, float) else None,
                space_before_pt=fmt.space_before.pt if fmt.space_before else None,
                space_after_pt=fmt.space_after.pt if fmt.space_after else None,
            )
        )

    styles = {
        style.name: {
            "style_id": style.style_id,
            "type": str(style.type),
            "base_style": _base_style_name(style),
        }
        for style in document.styles
        if style.name
    }
    if not paragraphs:
        warnings.append(ParseWarning(code="empty_document", message="文档没有可解析段落。"))

    return DocumentModel(
        document_id=document_id,
        source_filename=source_filename,
        package_parts=package_parts,
        sections=sections,
        paragraphs=paragraphs,
        table_count=len(document.tables),
        image_count=image_count,
        styles=styles,
        parse_warnings=warnings,
    )


def _base_style_name(style) -> str | None:
    base_style = getattr(style, "base_style", None)
    return base_style.name if base_style else None
