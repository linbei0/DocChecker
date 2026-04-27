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
    assert result.parse_warnings == []


def test_extract_rules_reports_warning_for_unrecognized_text() -> None:
    result = extract_rules_from_text("按学校要求执行。", source_type=SourceType.manual)

    assert result.rules == []
    assert result.parse_warnings


def test_extract_title_rule_from_comment_style_text() -> None:
    result = extract_rules_from_text(
        "三号宋体加粗居中，一般不多于30个字。",
        source_type=SourceType.requirement_doc,
    )

    title_rule = next(rule for rule in result.rules if rule.id == "title_format")

    assert title_rule.expectation["fontFamilyEastAsia"] == "宋体"
    assert title_rule.expectation["fontSizePt"] == 16
    assert title_rule.expectation["bold"] is True
