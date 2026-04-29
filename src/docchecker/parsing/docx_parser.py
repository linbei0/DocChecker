from pathlib import Path
from zipfile import ZipFile

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

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
    name = getattr(value, "name", None)
    if name:
        return name.lower()
    return str(value).split(".")[-1].split()[0].lower()


def _single_value(values: list[object]) -> object | None:
    if not values:
        return None
    first = values[0]
    if all(value == first for value in values):
        return first
    return None


def _style_chain(style) -> list[object]:
    styles: list[object] = []
    current = style
    while current is not None:
        styles.append(current)
        current = getattr(current, "base_style", None)
    return styles


def _font_name(font) -> str | None:
    if font.name:
        return font.name
    return _r_fonts_name(getattr(font, "_element", None))


def _r_fonts_name(element) -> str | None:
    r_fonts = getattr(element, "rFonts", None)
    if r_fonts is None and element is not None:
        r_fonts = element.find(qn("w:rFonts"))
    if r_fonts is None and element is not None:
        r_fonts = element.find(".//" + qn("w:rFonts"))
    if r_fonts is None:
        return None
    return (
        r_fonts.get(qn("w:eastAsia"))
        or r_fonts.get(qn("w:hAnsi"))
        or r_fonts.get(qn("w:ascii"))
    )


def _document_default_font_name(document) -> str | None:
    r_pr = document.styles.element.find(
        ".//" + qn("w:docDefaults") + "/" + qn("w:rPrDefault") + "/" + qn("w:rPr")
    )
    return _r_fonts_name(r_pr)


def _run_style_font_value(run, paragraph, field: str):
    value = getattr(run.font, field)
    if value is not None:
        return value
    for style in _style_chain(getattr(run, "style", None)):
        value = getattr(style.font, field)
        if value is not None:
            return value
    for style in _style_chain(getattr(paragraph, "style", None)):
        value = getattr(style.font, field)
        if value is not None:
            return value
    return None


def _run_style_bold(run, paragraph) -> bool | None:
    value = _run_style_font_value(run, paragraph, "bold")
    if value is not None:
        return bool(value)
    for element in [getattr(run.font, "_element", None)] + [
        style._element for style in _style_chain(getattr(run, "style", None))
    ] + [style._element for style in _style_chain(getattr(paragraph, "style", None))]:
        if _has_bool_property(element, "bCs"):
            return True
    return None


def _has_bool_property(element, name: str) -> bool:
    if element is None:
        return False
    node = element.find(".//" + qn(f"w:{name}"))
    if node is None:
        return False
    value = node.get(qn("w:val"))
    return value not in {"0", "false", "False"}


def _run_style_font_name(run, paragraph, default_font_name: str | None) -> str | None:
    value = _font_name(run.font)
    if value:
        return value
    for style in _style_chain(getattr(run, "style", None)):
        value = _font_name(style.font)
        if value:
            return value
    for style in _style_chain(getattr(paragraph, "style", None)):
        value = _font_name(style.font)
        if value:
            return value
    return default_font_name


def _font_size_pt(paragraph) -> float | None:
    sizes = [
        size.pt
        for run in paragraph.runs
        if (size := _run_style_font_value(run, paragraph, "size")) is not None
    ]
    return _single_value(sizes)


def _font_family(paragraph, default_font_name: str | None) -> str | None:
    names = [
        name
        for run in paragraph.runs
        if (name := _run_style_font_name(run, paragraph, default_font_name)) is not None
    ]
    return _single_value(names)


def _script_font_family(
    paragraph,
    default_font_name: str | None,
    *,
    script: str,
) -> str | None:
    names = [
        name
        for run in paragraph.runs
        if _run_contains_script(run.text, script)
        and (name := _run_style_font_name(run, paragraph, default_font_name)) is not None
    ]
    return _single_value(names)


def _script_font_families(
    paragraph,
    default_font_name: str | None,
    *,
    script: str,
) -> list[str]:
    names: list[str] = []
    for run in paragraph.runs:
        if not _run_contains_script(run.text, script):
            continue
        name = _run_style_font_name(run, paragraph, default_font_name)
        if name and name not in names:
            names.append(name)
    return names


def _run_contains_script(text: str, script: str) -> bool:
    if script == "east_asia":
        return any("\u4e00" <= char <= "\u9fff" for char in text)
    if script == "ascii":
        return any(char.isascii() and char.isalpha() for char in text)
    return False


def _bold(paragraph) -> bool | None:
    values = [
        value
        for run in paragraph.runs
        if (value := _run_style_bold(run, paragraph)) is not None
    ]
    return _single_value(values)


def _paragraph_format_value(paragraph, field: str):
    direct_value = getattr(paragraph.paragraph_format, field)
    if direct_value is not None:
        return direct_value
    for style in _style_chain(getattr(paragraph, "style", None)):
        value = getattr(style.paragraph_format, field)
        if value is not None:
            return value
    return None


def _line_spacing(paragraph) -> float | None:
    value = _paragraph_format_value(paragraph, "line_spacing")
    return value if isinstance(value, float) else None


def _space_pt(paragraph, field: str) -> float | None:
    value = _paragraph_format_value(paragraph, field)
    return value.pt if value is not None else None


def parse_docx(path: Path, *, document_id: str, source_filename: str) -> DocumentModel:
    package_parts: list[str]
    with ZipFile(path) as package:
        package_parts = package.namelist()
        image_count = len([name for name in package_parts if name.startswith("word/media/")])

    document = Document(path)
    default_font_name = _document_default_font_name(document)
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
    current_section_name: str | None = None
    for index, paragraph in enumerate(document.paragraphs):
        style_name = paragraph.style.name if paragraph.style else None
        text = paragraph.text
        if _is_heading_style(style_name) and text.strip():
            current_section_name = _compact_text(text, max_length=40)
        raw = {"section_name": current_section_name} if current_section_name else {}
        raw["font_family_east_asia_values"] = _script_font_families(
            paragraph,
            default_font_name,
            script="east_asia",
        )
        raw["font_family_ascii_values"] = _script_font_families(
            paragraph,
            default_font_name,
            script="ascii",
        )
        paragraphs.append(
            ParagraphNode(
                index=index,
                text=text,
                style_name=style_name,
                font_family=_font_family(paragraph, default_font_name),
                font_family_east_asia=_script_font_family(
                    paragraph,
                    default_font_name,
                    script="east_asia",
                ),
                font_family_ascii=_script_font_family(
                    paragraph,
                    default_font_name,
                    script="ascii",
                ),
                font_size_pt=_font_size_pt(paragraph),
                bold=_bold(paragraph),
                alignment=_alignment_name(_paragraph_format_value(paragraph, "alignment")),
                first_line_indent_cm=_emu_to_cm(
                    _paragraph_format_value(paragraph, "first_line_indent")
                ),
                line_spacing=_line_spacing(paragraph),
                space_before_pt=_space_pt(paragraph, "space_before"),
                space_after_pt=_space_pt(paragraph, "space_after"),
                raw=raw,
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


def _is_heading_style(style_name: str | None) -> bool:
    if not style_name:
        return False
    normalized = style_name.strip().lower()
    return normalized.startswith("heading") or normalized.startswith("标题")


def _compact_text(text: str, *, max_length: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[: max_length - 1]}…"
