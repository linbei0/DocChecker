import re
from pathlib import Path
from zipfile import ZipFile

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

from docchecker.domain.document import (
    AbstractFact,
    CaptionFact,
    DocumentFacts,
    DocumentModel,
    EffectiveFormatFact,
    FieldFact,
    HeaderFooterFact,
    HeaderFooterParagraphFact,
    LogicalSectionNode,
    NumberingFact,
    ParagraphNode,
    ParseWarning,
    ReferenceEntryFact,
    ReferenceFacts,
    RunSpan,
    SectionNode,
    StyleFact,
    TableCellFact,
    TableFact,
    TocFact,
)

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


def _font_name(font, *, script: str | None = None) -> str | None:
    r_fonts_name = _r_fonts_name(getattr(font, "_element", None), script=script)
    if script:
        return _clean_font_name(r_fonts_name or font.name)
    return _clean_font_name(font.name or r_fonts_name)


def _clean_font_name(value: str | None) -> str | None:
    if not value:
        return None
    return value.split(";")[0].strip() or None


def _r_fonts_name(element, *, script: str | None = None) -> str | None:
    r_fonts = getattr(element, "rFonts", None)
    if r_fonts is None and element is not None:
        r_fonts = element.find(qn("w:rFonts"))
    if r_fonts is None and element is not None:
        r_fonts = element.find(".//" + qn("w:rFonts"))
    if r_fonts is None:
        return None
    if script == "east_asia":
        return (
            r_fonts.get(qn("w:eastAsia"))
            or r_fonts.get(qn("w:hAnsi"))
            or r_fonts.get(qn("w:ascii"))
        )
    if script == "ascii":
        return (
            r_fonts.get(qn("w:ascii"))
            or r_fonts.get(qn("w:hAnsi"))
            or r_fonts.get(qn("w:eastAsia"))
        )
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


def _run_style_font_name(
    run,
    paragraph,
    default_font_name: str | None,
    *,
    script: str | None = None,
) -> str | None:
    value = _font_name(run.font, script=script)
    if value:
        return value
    for style in _style_chain(getattr(run, "style", None)):
        value = _font_name(style.font, script=script)
        if value:
            return value
    for style in _style_chain(getattr(paragraph, "style", None)):
        value = _font_name(style.font, script=script)
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
        and (
            name := _run_style_font_name(
                run,
                paragraph,
                default_font_name,
                script=script,
            )
        )
        is not None
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
        name = _run_style_font_name(
            run,
            paragraph,
            default_font_name,
            script=script,
        )
        if name and name not in names:
            names.append(name)
    return names


def _run_contains_script(text: str, script: str) -> bool:
    if script == "east_asia":
        return any("\u4e00" <= char <= "\u9fff" for char in text)
    if script == "ascii":
        return any(char.isascii() and char.isalpha() for char in text)
    return False


def _run_script(text: str) -> str:
    has_east_asia = _run_contains_script(text, "east_asia")
    has_ascii = _run_contains_script(text, "ascii")
    if has_east_asia and has_ascii:
        return "mixed"
    if has_east_asia:
        return "east_asia"
    if has_ascii:
        return "ascii"
    return "other"


def _run_spans(paragraph, default_font_name: str | None) -> list[RunSpan]:
    spans: list[RunSpan] = []
    for run in paragraph.runs:
        if not run.text:
            continue
        script = _run_script(run.text)
        font_family = _run_style_font_name(run, paragraph, default_font_name)
        size = _run_style_font_value(run, paragraph, "size")
        spans.append(
            RunSpan(
                text=run.text,
                script=script,
                font_family=font_family,
                font_family_east_asia=(
                    font_family if script in {"east_asia", "mixed"} else None
                ),
                font_family_ascii=font_family if script in {"ascii", "mixed"} else None,
                font_size_pt=size.pt if size is not None else None,
                bold=_run_style_bold(run, paragraph),
                style_name=run.style.name if getattr(run, "style", None) else None,
                source="resolved",
            )
        )
    return spans


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
        paragraph_format = getattr(style, "paragraph_format", None)
        if paragraph_format is None:
            continue
        value = getattr(paragraph_format, field)
        if value is not None:
            return value
    return None


def _paragraph_format_source(paragraph, field: str) -> str | None:
    if getattr(paragraph.paragraph_format, field) is not None:
        return "direct"
    for style in _style_chain(getattr(paragraph, "style", None)):
        paragraph_format = getattr(style, "paragraph_format", None)
        if paragraph_format is not None and getattr(paragraph_format, field) is not None:
            return f"paragraph_style:{style.name}"
    return None


def _font_value_source(paragraph, field: str, default_font_name: str | None) -> str | None:
    for run in paragraph.runs:
        if getattr(run.font, field) is not None:
            return "direct"
        for style in _style_chain(getattr(run, "style", None)):
            if getattr(style.font, field) is not None:
                return f"run_style:{style.name}"
        for style in _style_chain(getattr(paragraph, "style", None)):
            if getattr(style.font, field) is not None:
                return f"paragraph_style:{style.name}"
    if field == "name" and default_font_name:
        return "document_default"
    return None


def _line_spacing(paragraph) -> float | None:
    value = _paragraph_format_value(paragraph, "line_spacing")
    return value if isinstance(value, float) else None


def _space_pt(paragraph, field: str) -> float | None:
    value = _paragraph_format_value(paragraph, field)
    return value.pt if value is not None else None


def _effective_format_values(paragraph, default_font_name: str | None) -> dict[str, object]:
    values = {
        "font_family": _font_family(paragraph, default_font_name),
        "font_family_east_asia": _script_font_family(
            paragraph,
            default_font_name,
            script="east_asia",
        ),
        "font_family_ascii": _script_font_family(
            paragraph,
            default_font_name,
            script="ascii",
        ),
        "font_size_pt": _font_size_pt(paragraph),
        "bold": _bold(paragraph),
        "alignment": _alignment_name(_paragraph_format_value(paragraph, "alignment")),
        "first_line_indent_cm": _emu_to_cm(
            _paragraph_format_value(paragraph, "first_line_indent")
        ),
        "line_spacing": _line_spacing(paragraph),
        "space_before_pt": _space_pt(paragraph, "space_before"),
        "space_after_pt": _space_pt(paragraph, "space_after"),
    }
    return {key: value for key, value in values.items() if value is not None}


def _effective_format_sources(paragraph, default_font_name: str | None) -> dict[str, str | None]:
    return {
        "font_family": _font_value_source(paragraph, "name", default_font_name),
        "font_size_pt": _font_value_source(paragraph, "size", default_font_name),
        "bold": _font_value_source(paragraph, "bold", default_font_name),
        "alignment": _paragraph_format_source(paragraph, "alignment"),
        "first_line_indent_cm": _paragraph_format_source(paragraph, "first_line_indent"),
        "line_spacing": _paragraph_format_source(paragraph, "line_spacing"),
        "space_before_pt": _paragraph_format_source(paragraph, "space_before"),
        "space_after_pt": _paragraph_format_source(paragraph, "space_after"),
    }


def parse_docx(path: Path, *, document_id: str, source_filename: str) -> DocumentModel:
    package_parts: list[str]
    with ZipFile(path) as package:
        package_parts = package.namelist()
        image_count = len([name for name in package_parts if name.startswith("word/media/")])
        xml_parts = {
            name: package.read(name).decode("utf-8", errors="replace")
            for name in package_parts
            if name.startswith("word/") and name.endswith(".xml")
        }

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
        raw["effective_format"] = _effective_format_values(paragraph, default_font_name)
        raw["effective_format_sources"] = _effective_format_sources(
            paragraph,
            default_font_name,
        )
        runs = _run_spans(paragraph, default_font_name)
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
                runs=runs,
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

    logical_sections = _build_logical_sections(paragraphs)
    table_facts = _table_facts(document, paragraphs)
    field_facts = [
        fact
        for index, paragraph in enumerate(document.paragraphs)
        for fact in _field_facts(paragraph, index)
    ]

    facts = DocumentFacts(
        xml_parts=xml_parts,
        headers_footers=_header_footer_facts(document, default_font_name),
        tables=table_facts,
        captions=_caption_facts(paragraphs, table_facts),
        toc=_toc_fact(paragraphs, field_facts),
        numbering=[
            fact
            for index, paragraph in enumerate(document.paragraphs)
            if (fact := _numbering_fact(paragraph, index)) is not None
        ],
        fields=field_facts,
        styles=_style_facts(document),
        effective_formats=_effective_format_facts(paragraphs),
        references=_reference_facts(paragraphs, logical_sections),
        abstracts=_abstract_facts(paragraphs, logical_sections),
    )

    return DocumentModel(
        document_id=document_id,
        source_filename=source_filename,
        package_parts=package_parts,
        sections=sections,
        logical_sections=logical_sections,
        paragraphs=paragraphs,
        table_count=len(document.tables),
        image_count=image_count,
        styles=styles,
        facts=facts,
        parse_warnings=warnings,
    )


def _header_footer_facts(
    document,
    default_font_name: str | None,
) -> list[HeaderFooterFact]:
    facts: list[HeaderFooterFact] = []
    for section_index, section in enumerate(document.sections):
        for kind, part in [
            ("header.default", section.header),
            ("footer.default", section.footer),
            ("header.first_page", section.first_page_header),
            ("footer.first_page", section.first_page_footer),
            ("header.even_page", section.even_page_header),
            ("footer.even_page", section.even_page_footer),
        ]:
            paragraphs = list(part.paragraphs)
            text = "\n".join(paragraph.text for paragraph in paragraphs if paragraph.text.strip())
            paragraph_facts = [
                HeaderFooterParagraphFact(
                    section_index=section_index,
                    kind=kind,
                    index=paragraph_index,
                    text=paragraph.text,
                    style_name=paragraph.style.name if paragraph.style else None,
                    effective_format=_effective_format_values(paragraph, default_font_name),
                    effective_format_sources=_effective_format_sources(
                        paragraph,
                        default_font_name,
                    ),
                )
                for paragraph_index, paragraph in enumerate(paragraphs)
            ]
            facts.append(
                HeaderFooterFact(
                    section_index=section_index,
                    kind=kind,
                    text=text,
                    inherited=bool(getattr(part, "is_linked_to_previous", False)),
                    paragraph_count=len(paragraphs),
                    paragraphs=paragraph_facts,
                )
            )
    return facts


def _table_facts(document, paragraphs: list[ParagraphNode]) -> list[TableFact]:
    facts: list[TableFact] = []
    anchors = _table_anchor_indices(document)
    for table_index, table in enumerate(document.tables):
        preceding_index, following_index = anchors.get(table_index, (None, None))
        caption_text, caption_position = _table_caption(
            paragraphs,
            preceding_index,
            following_index,
        )
        cells = [
            TableCellFact(
                row_index=row_index,
                column_index=column_index,
                text=cell.text,
            )
            for row_index, row in enumerate(table.rows)
            for column_index, cell in enumerate(row.cells)
        ]
        facts.append(
            TableFact(
                index=table_index,
                row_count=len(table.rows),
                column_count=len(table.columns),
                cells=cells,
                caption_text=caption_text,
                caption_position=caption_position,
                preceding_paragraph_index=preceding_index,
                following_paragraph_index=following_index,
            )
        )
    return facts


def _table_anchor_indices(document) -> dict[int, tuple[int | None, int | None]]:
    anchors: dict[int, tuple[int | None, int | None]] = {}
    table_index = 0
    paragraph_index = 0
    block_order: list[tuple[str, int]] = []
    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            block_order.append(("paragraph", paragraph_index))
            paragraph_index += 1
        elif child.tag == qn("w:tbl"):
            block_order.append(("table", table_index))
            table_index += 1
    for block_position, (kind, index) in enumerate(block_order):
        if kind != "table":
            continue
        previous_paragraph = next(
            (
                item_index
                for item_kind, item_index in reversed(block_order[:block_position])
                if item_kind == "paragraph"
            ),
            None,
        )
        next_paragraph = next(
            (
                item_index
                for item_kind, item_index in block_order[block_position + 1 :]
                if item_kind == "paragraph"
            ),
            None,
        )
        anchors[index] = (previous_paragraph, next_paragraph)
    return anchors


def _table_caption(
    paragraphs: list[ParagraphNode],
    preceding_index: int | None,
    following_index: int | None,
) -> tuple[str | None, str | None]:
    if preceding_index is not None and _is_table_caption_text(paragraphs[preceding_index].text):
        return paragraphs[preceding_index].text, "before"
    if following_index is not None and _is_table_caption_text(paragraphs[following_index].text):
        return paragraphs[following_index].text, "after"
    return None, None


def _is_table_caption_text(text: str) -> bool:
    return bool(re.match(r"^\s*表\s*\d+(?:[.\-]\d+)*", text))


def _caption_facts(
    paragraphs: list[ParagraphNode],
    tables: list[TableFact],
) -> list[CaptionFact]:
    linked_tables: dict[int, tuple[str, int]] = {}
    for table in tables:
        if table.caption_position == "before" and table.preceding_paragraph_index is not None:
            linked_tables[table.preceding_paragraph_index] = ("before", table.index)
        if table.caption_position == "after" and table.following_paragraph_index is not None:
            linked_tables[table.following_paragraph_index] = ("after", table.index)

    facts: list[CaptionFact] = []
    for paragraph in paragraphs:
        kind = _caption_kind(paragraph.text)
        if kind is None:
            continue
        position, target_index = linked_tables.get(paragraph.index, ("standalone", None))
        facts.append(
            CaptionFact(
                kind=kind,
                text=paragraph.text.strip(),
                paragraph_index=paragraph.index,
                position=position,
                target_index=target_index,
            )
        )
    return facts


def _caption_kind(text: str) -> str | None:
    if re.match(r"^\s*表\s*\d+(?:[.\-]\d+)*", text):
        return "table"
    if re.match(r"^\s*图\s*\d+(?:[.\-]\d+)*", text):
        return "figure"
    return None


def _toc_fact(paragraphs: list[ParagraphNode], fields: list[FieldFact]) -> TocFact:
    title_index = next(
        (
            paragraph.index
            for paragraph in paragraphs
            if _normalize_section_text(paragraph.text) in {"目录", "目次"}
        ),
        None,
    )
    entry_indices = [
        paragraph.index for paragraph in paragraphs if _is_toc_entry(paragraph)
    ]
    return TocFact(
        has_title=title_index is not None,
        has_field=any(field.field_type == "TOC" for field in fields),
        entry_count=len(entry_indices),
        title_paragraph_index=title_index,
        entry_paragraph_indices=entry_indices,
    )


def _numbering_fact(paragraph, index: int) -> NumberingFact | None:
    p_pr = getattr(paragraph._p, "pPr", None)
    num_pr = getattr(p_pr, "numPr", None) if p_pr is not None else None
    if num_pr is None:
        return None
    num_id = getattr(num_pr, "numId", None)
    ilvl = getattr(num_pr, "ilvl", None)
    return NumberingFact(
        paragraph_index=index,
        num_id=str(num_id.val) if num_id is not None else None,
        level=str(ilvl.val) if ilvl is not None else None,
        style_name=paragraph.style.name if paragraph.style else None,
        text=paragraph.text,
    )


def _field_facts(paragraph, index: int) -> list[FieldFact]:
    facts: list[FieldFact] = []
    simple_fields = paragraph._p.findall(".//" + qn("w:fldSimple"))
    for node in simple_fields:
        instruction = (node.get(qn("w:instr")) or "").strip()
        if not instruction:
            continue
        facts.append(
            FieldFact(
                paragraph_index=index,
                field_type=instruction.split()[0].upper(),
                instruction=instruction,
                text=paragraph.text or None,
            )
        )
    for node in paragraph._p.iter(qn("w:instrText")):
        instruction = "".join(node.itertext()).strip()
        if not instruction:
            continue
        field_type = instruction.split()[0].upper()
        facts.append(
            FieldFact(
                paragraph_index=index,
                field_type=field_type,
                instruction=instruction,
                text=paragraph.text or None,
            )
        )
    return facts


def _reference_facts(
    paragraphs: list[ParagraphNode],
    logical_sections: list[LogicalSectionNode],
) -> ReferenceFacts:
    reference_section = next(
        (section for section in logical_sections if section.role == "references"),
        None,
    )
    if reference_section is None:
        candidate_paragraphs = paragraphs
    else:
        end_index = reference_section.end_paragraph_index or paragraphs[-1].index
        candidate_paragraphs = [
            paragraph
            for paragraph in paragraphs
            if reference_section.start_paragraph_index < paragraph.index <= end_index
        ]
    entries = [
        ReferenceEntryFact(
            paragraph_index=paragraph.index,
            number=_reference_number(paragraph.text),
            text=paragraph.text,
        )
        for paragraph in candidate_paragraphs
        if _reference_number(paragraph.text) is not None
    ]
    numbers = [entry.number for entry in entries]
    expected = list(range(1, len(entries) + 1))
    return ReferenceFacts(
        has_section=reference_section is not None,
        section_start_paragraph_index=(
            reference_section.start_paragraph_index if reference_section else None
        ),
        entry_count=len(entries),
        numbering_continuous=bool(entries) and numbers == expected,
        entries=entries,
    )


def _reference_number(text: str) -> int | None:
    match = re.match(r"^\s*\[(\d+)]", text)
    return int(match.group(1)) if match else None


def _abstract_facts(
    paragraphs: list[ParagraphNode],
    logical_sections: list[LogicalSectionNode],
) -> list[AbstractFact]:
    facts: list[AbstractFact] = []
    for section_index, section in enumerate(logical_sections):
        if section.role != "abstract":
            continue
        end_index = section.end_paragraph_index or paragraphs[-1].index
        content_paragraphs = [
            paragraph
            for paragraph in paragraphs
            if section.start_paragraph_index < paragraph.index <= end_index
        ]
        keyword = next(
            (
                paragraph.text.strip()
                for paragraph in content_paragraphs
                if _is_keyword_paragraph(paragraph.text)
            ),
            None,
        )
        if keyword is None:
            keyword = _following_keyword_text(paragraphs, logical_sections, section_index)
        content_text = "\n".join(
            paragraph.text.strip()
            for paragraph in content_paragraphs
            if paragraph.text.strip() and not _is_keyword_paragraph(paragraph.text)
        )
        facts.append(
            AbstractFact(
                language=_abstract_language(section.title),
                title_paragraph_index=section.start_paragraph_index,
                content_text=content_text,
                word_count=_abstract_word_count(content_text),
                keyword_text=keyword,
                keyword_count=_keyword_count(keyword),
                has_keywords=keyword is not None,
            )
        )
    return facts


def _following_keyword_text(
    paragraphs: list[ParagraphNode],
    logical_sections: list[LogicalSectionNode],
    section_index: int,
) -> str | None:
    if section_index + 1 >= len(logical_sections):
        return None
    next_section = logical_sections[section_index + 1]
    if next_section.role != "keywords":
        return None
    end_index = next_section.end_paragraph_index or paragraphs[-1].index
    return next(
        (
            paragraph.text.strip()
            for paragraph in paragraphs
            if next_section.start_paragraph_index <= paragraph.index <= end_index
            and _is_keyword_paragraph(paragraph.text)
        ),
        None,
    )


def _abstract_language(title: str) -> str:
    normalized = title.lower()
    if "英文" in title or "abstract" in normalized:
        return "en"
    return "zh"


def _abstract_word_count(text: str) -> int:
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
    ascii_words = re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)?", text)
    return len(chinese_chars) + len(ascii_words)


def _is_keyword_paragraph(text: str) -> bool:
    normalized = _normalize_section_text(text)
    return (
        normalized.startswith("关键词")
        or normalized.startswith("关键字")
        or normalized.startswith("keywords")
        or normalized.startswith("key words")
    )


def _keyword_count(text: str | None) -> int:
    if not text:
        return 0
    values = re.sub(
        r"^\s*(关键词|关键字|keywords|key words)\s*[:：]?",
        "",
        text,
        flags=re.I,
    )
    parts = [part.strip() for part in re.split(r"[;；,，、\s]+", values) if part.strip()]
    return len(parts)


def _effective_format_facts(paragraphs: list[ParagraphNode]) -> list[EffectiveFormatFact]:
    return [
        EffectiveFormatFact(
            owner_type="paragraph",
            owner_id=f"paragraph:{paragraph.index}",
            paragraph_index=paragraph.index,
            section_index=paragraph.section_index,
            style_name=paragraph.style_name,
            values=paragraph.raw.get("effective_format", {}),
            sources=paragraph.raw.get("effective_format_sources", {}),
        )
        for paragraph in paragraphs
    ]


def _style_facts(document) -> list[StyleFact]:
    facts: list[StyleFact] = []
    for style in document.styles:
        if not style.name:
            continue
        paragraph_format = getattr(style, "paragraph_format", None)
        font = getattr(style, "font", None)
        formatting = {
            "fontFamily": _font_name(font) if font is not None else None,
            "fontFamilyEastAsia": _font_name(font, script="east_asia")
            if font is not None
            else None,
            "fontSizePt": font.size.pt if font is not None and font.size is not None else None,
            "bold": font.bold if font is not None else None,
            "alignment": _alignment_name(paragraph_format.alignment)
            if paragraph_format is not None
            else None,
            "spaceBeforePt": paragraph_format.space_before.pt
            if paragraph_format is not None and paragraph_format.space_before is not None
            else None,
            "spaceAfterPt": paragraph_format.space_after.pt
            if paragraph_format is not None and paragraph_format.space_after is not None
            else None,
        }
        facts.append(
            StyleFact(
                name=style.name,
                style_id=style.style_id,
                type=str(style.type),
                base_style=_base_style_name(style),
                formatting={key: value for key, value in formatting.items() if value is not None},
            )
        )
    return facts


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


SECTION_ROLE_ALIASES = {
    "abstract": ("中文摘要", "摘要", "摘 要", "abstract"),
    "keywords": ("中文关键词", "关键词", "关键字", "keywords", "key words"),
    "toc": ("目录", "目 录", "目  录"),
    "body": ("正文",),
    "acknowledgements": ("致谢", "致 谢", "谢辞"),
    "references": ("参考文献", "references", "bibliography"),
    "appendix": ("附录", "appendix"),
}


def _build_logical_sections(paragraphs: list[ParagraphNode]) -> list[LogicalSectionNode]:
    sections: list[LogicalSectionNode] = []
    for paragraph in paragraphs:
        role = _section_role(paragraph)
        if role is None:
            continue
        title = _compact_text(paragraph.text.strip(), max_length=80)
        if sections and sections[-1].role == role:
            continue
        if sections and sections[-1].end_paragraph_index is None:
            sections[-1].end_paragraph_index = paragraph.index - 1
        sections.append(
            LogicalSectionNode(
                role=role,
                title=title,
                start_paragraph_index=paragraph.index,
            )
        )
    if sections and sections[-1].end_paragraph_index is None:
        sections[-1].end_paragraph_index = paragraphs[-1].index if paragraphs else 0
    return sections


def _section_role(paragraph: ParagraphNode) -> str | None:
    text = paragraph.text.strip()
    if not text or _is_toc_entry(paragraph):
        return None
    normalized = _normalize_section_text(text)
    for role, aliases in SECTION_ROLE_ALIASES.items():
        for alias in aliases:
            alias_text = _normalize_section_text(alias)
            if normalized == alias_text or normalized.startswith(alias_text):
                return role
    if _is_heading_style(paragraph.style_name):
        return "body"
    if re.match(r"^\d+(?:\.\d+){0,3}\s+\S{1,80}$", text):
        return "body"
    return None


def _is_toc_entry(paragraph: ParagraphNode) -> bool:
    style_name = (paragraph.style_name or "").lower()
    if style_name.startswith("toc") or "目录" in style_name:
        return _normalize_section_text(paragraph.text) != _normalize_section_text("目录")
    return bool(re.match(r"^\d+(?:\.\d+){0,3}\s+.+\s+\d+$", paragraph.text.strip()))


def _normalize_section_text(value: str) -> str:
    return re.sub(r"[\s　:：]+", "", value).lower()
