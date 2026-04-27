from docchecker.domain.enums import SourceType
from docchecker.services.rule_extractor import extract_rules_from_text


def test_extract_rules_from_manual_text() -> None:
    result = extract_rules_from_text(
        "正文宋体小四，1.5倍行距，首行缩进2字符，页边距上下2.5cm。",
        source_type=SourceType.manual,
    )

    rule_ids = {rule.id for rule in result.rules}

    assert "body_font" in rule_ids
    assert "body_line_spacing" in rule_ids
    assert "body_first_line_indent" in rule_ids
    assert "page_margin_top" in rule_ids
    assert result.extraction_summary.structured_rules >= 4
    assert result.parse_warnings == []


def test_extract_rules_reports_warning_for_unrecognized_text() -> None:
    result = extract_rules_from_text("按学校要求执行。", source_type=SourceType.manual)

    assert result.rules == []
    assert result.parse_warnings
    assert result.extraction_summary.structured_rules == 0


def test_extract_title_rule_from_comment_style_text() -> None:
    result = extract_rules_from_text(
        "三号宋体加粗居中，一般不多于30个字。",
        source_type=SourceType.requirement_doc,
    )

    title_rule = next(rule for rule in result.rules if rule.id == "title_format")

    assert title_rule.expectation["fontFamilyEastAsia"] == "宋体"
    assert title_rule.expectation["fontSizePt"] == 16
    assert title_rule.expectation["bold"] is True


def test_extract_rules_keeps_requirement_locations() -> None:
    result = extract_rules_from_text(
        "paragraph:1\t正文宋体小四。\n"
        "table:1,row:2\t页边距：上2.5cm，下2.0cm，左3cm，右2cm。",
        source_type=SourceType.requirement_doc,
    )

    body_rule = next(rule for rule in result.rules if rule.id == "body_font")
    left_margin = next(rule for rule in result.rules if rule.id == "page_margin_left")

    assert body_rule.source.location == "paragraph:1"
    assert left_margin.source.location == "table:1,row:2"
    assert left_margin.expectation["margin_left_cm"] == 3


def test_extract_rules_reports_unsupported_requirements() -> None:
    result = extract_rules_from_text(
        "参考文献按 GB/T 7714 编排。\n目录自动生成，列至三级标题。",
        source_type=SourceType.requirement_doc,
    )

    categories = {item.category for item in result.unsupported_requirements}

    assert "reference" in categories
    assert "toc" in categories
    assert result.extraction_summary.unsupported_requirements == 2
    assert result.parse_warnings


def test_extract_rules_from_golden_corpus() -> None:
    samples = [
        (
            "论文题目三号黑体加粗居中。正文宋体小四，1.5倍行距，首行缩进2字符。",
            {"title_format", "body_font", "body_line_spacing", "body_first_line_indent"},
        ),
        (
            "一级标题黑体三号加粗居中；二级标题黑体小三加粗；三级标题宋体四号加粗。",
            {"heading1_font", "heading2_font", "heading3_font"},
        ),
        (
            "A4纸，页边距上2.5cm，下2.5cm，左3cm，右2cm，页眉1.5cm，页脚1.75cm。",
            {
                "page_size_a4",
                "page_margin_top",
                "page_margin_bottom",
                "page_margin_left",
                "page_margin_right",
                "page_header_distance",
                "page_footer_distance",
            },
        ),
        (
            "摘要宋体小四，关键词宋体小四。正文段前6磅，段后6磅。",
            {"abstract_font", "keywords_font", "body_paragraph_spacing"},
        ),
        (
            "正文宋体小四。图题、表题采用五号宋体；参考文献按学校规范著录。",
            {"body_font"},
        ),
    ]

    for text, expected_rule_ids in samples:
        result = extract_rules_from_text(text, source_type=SourceType.manual)
        rule_ids = {rule.id for rule in result.rules}

        assert expected_rule_ids <= rule_ids
