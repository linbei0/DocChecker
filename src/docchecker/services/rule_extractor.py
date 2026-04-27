import re
from dataclasses import dataclass

from docchecker.domain.enums import RuleCategory, Severity, SourceType
from docchecker.domain.rules import FormatRule, RuleSource, RuleTarget


@dataclass(frozen=True)
class RuleExtractionResult:
    rules: list[FormatRule]
    parse_warnings: list[str]


FONT_SIZE_BY_NAME = {
    "初号": 42,
    "小初": 36,
    "一号": 26,
    "小一": 24,
    "二号": 22,
    "小二": 18,
    "三号": 16,
    "小三": 15,
    "四号": 14,
    "小四": 12,
    "五号": 10.5,
    "小五": 9,
    "六号": 7.5,
    "小六": 6.5,
    "七号": 5.5,
    "八号": 5,
}


def extract_rules_from_text(text: str, *, source_type: SourceType) -> RuleExtractionResult:
    normalized = re.sub(r"\s+", " ", text.strip())
    rules: list[FormatRule] = []
    if not normalized:
        return RuleExtractionResult(rules=[], parse_warnings=["规则来源文本为空，未生成候选规则。"])

    rules.extend(_extract_body_font_rules(normalized, source_type))
    rules.extend(_extract_line_spacing_rules(normalized, source_type))
    rules.extend(_extract_first_line_indent_rules(normalized, source_type))
    rules.extend(_extract_margin_rules(normalized, source_type))
    rules.extend(_extract_heading_rules(normalized, source_type))
    rules.extend(_extract_title_rules(normalized, source_type))

    warnings = (
        []
        if rules
        else ["未识别到明确的格式规则，请补充字体、字号、行距、缩进或页边距要求。"]
    )
    return RuleExtractionResult(rules=_dedupe_rules(rules), parse_warnings=warnings)


def _extract_body_font_rules(text: str, source_type: SourceType) -> list[FormatRule]:
    rules: list[FormatRule] = []
    body_sentence = _sentence_containing(text, ["正文"])
    if not body_sentence:
        return rules
    expectation: dict[str, object] = {}
    font_family = _first_font_family(body_sentence)
    font_size = _first_font_size(body_sentence)
    if font_family:
        expectation["fontFamilyEastAsia"] = font_family
    if font_size:
        expectation["fontSizePt"] = font_size
    if "加粗" in body_sentence:
        expectation["bold"] = True
    if expectation:
        rules.append(
            _rule(
                "body_font",
                RuleCategory.font,
                "body.paragraph",
                "正文",
                expectation,
                body_sentence,
                source_type,
                Severity.major,
            )
        )
    return rules


def _extract_line_spacing_rules(text: str, source_type: SourceType) -> list[FormatRule]:
    sentence = _sentence_containing(text, ["行距"])
    if not sentence:
        return []
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:倍)?行距", sentence)
    if not match:
        return []
    return [
        _rule(
            "body_line_spacing",
            RuleCategory.paragraph,
            "body.paragraph",
            "正文",
            {"lineSpacing": float(match.group(1))},
            sentence,
            source_type,
            Severity.major,
        )
    ]


def _extract_first_line_indent_rules(text: str, source_type: SourceType) -> list[FormatRule]:
    sentence = _sentence_containing(text, ["首行缩进"])
    if not sentence:
        return []
    match = re.search(r"首行缩进\s*([0-9]+(?:\.[0-9]+)?)\s*(?:字符|字)", sentence)
    if not match:
        return []
    # 中文论文规范常用“2 字符”，按小四正文约 0.74cm 估算，报告中仍展示来源证据。
    indent_cm = round(float(match.group(1)) * 0.37, 2)
    return [
        _rule(
            "body_first_line_indent",
            RuleCategory.paragraph,
            "body.paragraph",
            "正文",
            {"firstLineIndentCm": indent_cm},
            sentence,
            source_type,
            Severity.major,
        )
    ]


def _extract_margin_rules(text: str, source_type: SourceType) -> list[FormatRule]:
    sentence = _sentence_containing(text, ["页边距", "页边距上", "页边距下"])
    if not sentence:
        return []
    rules: list[FormatRule] = []
    pair_match = re.search(r"页边距.*?上下\s*([0-9]+(?:\.[0-9]+)?)\s*cm", sentence, re.I)
    if pair_match:
        value = float(pair_match.group(1))
        rules.extend(
            [
                _page_rule("page_margin_top", "margin_top_cm", value, sentence, source_type),
                _page_rule("page_margin_bottom", "margin_bottom_cm", value, sentence, source_type),
            ]
        )
    for label, field, rule_id in [
        ("上", "margin_top_cm", "page_margin_top"),
        ("下", "margin_bottom_cm", "page_margin_bottom"),
        ("左", "margin_left_cm", "page_margin_left"),
        ("右", "margin_right_cm", "page_margin_right"),
    ]:
        match = re.search(rf"{label}\s*([0-9]+(?:\.[0-9]+)?)\s*cm", sentence, re.I)
        if match and not any(rule.id == rule_id for rule in rules):
            rules.append(_page_rule(rule_id, field, float(match.group(1)), sentence, source_type))
    return rules


def _extract_heading_rules(text: str, source_type: SourceType) -> list[FormatRule]:
    rules: list[FormatRule] = []
    for label, rule_id, scope, selector in [
        ("一级标题", "heading1_font", "heading.1", "一级标题"),
        ("二级标题", "heading2_font", "heading.2", "二级标题"),
        ("三级标题", "heading3_font", "heading.3", "三级标题"),
    ]:
        sentence = _sentence_containing(text, [label])
        if not sentence:
            continue
        expectation: dict[str, object] = {}
        font_family = _first_font_family(sentence)
        font_size = _first_font_size(sentence)
        if font_family:
            expectation["fontFamilyEastAsia"] = font_family
        if font_size:
            expectation["fontSizePt"] = font_size
        if "加粗" in sentence or "黑体" in sentence:
            expectation["bold"] = True
        if expectation:
            rules.append(
                _rule(
                    rule_id,
                    RuleCategory.heading,
                    scope,
                    selector,
                    expectation,
                    sentence,
                    source_type,
                    Severity.major,
                )
            )
    return rules


def _extract_title_rules(text: str, source_type: SourceType) -> list[FormatRule]:
    sentence = _sentence_containing(text, ["论文题目", "中文论文题目", "学士学位论文"])
    if not sentence:
        sentence = _sentence_containing(text, ["居中"])
        if not sentence or not _first_font_size(sentence):
            return []

    expectation: dict[str, object] = {}
    font_family = _first_font_family(sentence)
    font_size = _first_font_size(sentence)
    if font_family:
        expectation["fontFamilyEastAsia"] = font_family
    if font_size:
        expectation["fontSizePt"] = font_size
    if "加粗" in sentence or "黑体" in sentence:
        expectation["bold"] = True
    if "居中" in sentence:
        expectation["alignment"] = "center"
    if not expectation:
        return []

    return [
        _rule(
            "title_format",
            RuleCategory.font,
            "cover.title",
            "论文题目",
            expectation,
            sentence,
            source_type,
            Severity.major,
        )
    ]


def _first_font_family(text: str) -> str | None:
    for family in ["宋体", "黑体", "楷体", "仿宋", "微软雅黑", "Times New Roman"]:
        if family in text:
            return family
    return None


def _first_font_size(text: str) -> float | None:
    for name, value in FONT_SIZE_BY_NAME.items():
        if name in text:
            return value
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:pt|磅)", text, re.I)
    return float(match.group(1)) if match else None


def _sentence_containing(text: str, keywords: list[str]) -> str | None:
    parts = re.split(r"[。；;\n\r]", text)
    for part in parts:
        if any(keyword in part for keyword in keywords):
            return part.strip()
    return text.strip() if any(keyword in text for keyword in keywords) else None


def _page_rule(
    rule_id: str,
    field: str,
    value: float,
    excerpt: str,
    source_type: SourceType,
) -> FormatRule:
    return _rule(
        rule_id,
        RuleCategory.page,
        "document",
        "整篇文档",
        {field: value},
        excerpt,
        source_type,
        Severity.minor,
        {
            "margin_top_cm": 0.1,
            "margin_bottom_cm": 0.1,
            "margin_left_cm": 0.1,
            "margin_right_cm": 0.1,
        },
    )


def _rule(
    rule_id: str,
    category: RuleCategory,
    scope: str,
    selector: str,
    expectation: dict[str, object],
    excerpt: str,
    source_type: SourceType,
    severity: Severity,
    tolerance: dict[str, object] | None = None,
) -> FormatRule:
    return FormatRule(
        id=rule_id,
        category=category,
        target=RuleTarget(scope=scope, selector=selector),
        expectation=expectation,
        tolerance=tolerance or {},
        severity=severity,
        source=RuleSource(type=source_type, excerpt=excerpt[:300], location=None),
        confidence=0.85,
        enabled=True,
    )


def _dedupe_rules(rules: list[FormatRule]) -> list[FormatRule]:
    seen: set[str] = set()
    deduped: list[FormatRule] = []
    for rule in rules:
        if rule.id in seen:
            continue
        seen.add(rule.id)
        deduped.append(rule)
    return deduped
