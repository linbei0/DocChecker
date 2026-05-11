from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

from docchecker.domain.document import RunSpan

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


ParagraphLocator = dict[str, str | int | None]


