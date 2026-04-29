import json

import pytest

from docchecker.domain.enums import SourceType
from docchecker.services.rule_extractor import (
    RuleExtractionConfigurationError,
    extract_rules_from_text,
)


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


def test_extract_rules_maps_semantic_requirements_to_checkable_rules() -> None:
    result = extract_rules_from_text(
        "参考文献按 GB/T 7714 编排。\n目录自动生成，列至三级标题。",
        source_type=SourceType.requirement_doc,
    )

    rule_ids = {rule.id for rule in result.rules}

    assert "reference_basic_entries" in rule_ids
    assert "toc_basic_shape" in rule_ids
    assert result.extraction_summary.unsupported_requirements == 0


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


def test_hybrid_mode_requires_explicit_llm_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOC_CHECKER_RULE_EXTRACTOR_MODE", "hybrid")
    monkeypatch.setenv("DOC_CHECKER_LLM_API_BASE", "")
    monkeypatch.setenv("DOC_CHECKER_LLM_API_KEY", "")
    monkeypatch.setenv("DOC_CHECKER_LLM_MODEL", "")

    from docchecker.core.config import get_settings

    get_settings.cache_clear()
    try:
        with pytest.raises(RuleExtractionConfigurationError):
            extract_rules_from_text("目录自动生成。", source_type=SourceType.requirement_doc)
    finally:
        get_settings.cache_clear()


def test_hybrid_mode_accepts_schema_compliant_llm_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, request_payload = _extract_with_mocked_llm(
        monkeypatch,
        {
            "rule_candidates": [
                {
                    "category": "structure",
                    "target_scope": "document.structure",
                    "selector": "论文结构",
                    "expectation": {"requiredSections": ["中文摘要", "正文"]},
                    "evidence_span": "论文应包括中文摘要和正文。",
                    "location": "paragraph:42",
                    "checkability": "checkable",
                    "confidence": 0.8,
                    "reason": None,
                }
            ]
        },
    )

    system_prompt = request_payload["messages"][0]["content"]
    assert "category 只能是 page" in system_prompt
    assert "checkability 只能是 checkable" in system_prompt
    assert "expectation 必须是 JSON object" in system_prompt
    assert "structure_required_sections" in {rule.id for rule in result.rules}
    assert result.extraction_trace is not None
    assert result.extraction_trace.issues == []


def test_hybrid_mode_rejects_invalid_llm_candidate_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, _ = _extract_with_mocked_llm(
        monkeypatch,
        {
            "rule_candidates": [
                {
                    "category": "abstract_word_count",
                    "target_scope": "abstract",
                    "selector": "中文摘要",
                    "expectation": "中文摘要要求300字左右",
                    "evidence_span": "中文摘要要求300字左右。",
                    "location": "paragraph:42",
                    "checkability": "specific",
                    "confidence": 0.8,
                }
            ]
        },
    )

    assert result.rules == []
    assert result.extraction_trace is not None
    assert len(result.extraction_trace.issues) == 1
    issue = result.extraction_trace.issues[0]
    assert issue.reason_code == "invalid_llm_response"
    assert issue.message == (
        "LLM 返回的规则候选格式不符合系统 schema，"
        "已拒绝本次 LLM 候选；本地规则抽取结果仍可使用。"
    )
    assert issue.excerpt is not None
    assert "abstract_word_count" in issue.excerpt
    assert "validation errors" not in issue.message


def test_hybrid_mode_drops_unsupported_llm_expectation_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, _ = _extract_with_mocked_llm(
        monkeypatch,
        {
            "rule_candidates": [
                {
                    "category": "heading",
                    "target_scope": "heading.level1",
                    "selector": "一级标题",
                    "expectation": {
                        "fontSizePt": 12,
                        "spaceBetweenNumberAndTitle": True,
                    },
                    "evidence_span": "一级标题字号12，序号和标题之间空1格。",
                    "location": "paragraph:1",
                    "checkability": "checkable",
                    "confidence": 0.8,
                }
            ]
        },
    )

    rule = next(rule for rule in result.rules if rule.id == "heading_candidate")

    assert rule.expectation == {"fontSizePt": 12}


def _extract_with_mocked_llm(
    monkeypatch: pytest.MonkeyPatch,
    llm_content: dict[str, object],
):
    monkeypatch.setenv("DOC_CHECKER_RULE_EXTRACTOR_MODE", "hybrid")
    monkeypatch.setenv("DOC_CHECKER_LLM_API_BASE", "https://llm.example.test")
    monkeypatch.setenv("DOC_CHECKER_LLM_API_KEY", "test-key")
    monkeypatch.setenv("DOC_CHECKER_LLM_MODEL", "test-model")

    from docchecker.core.config import get_settings

    get_settings.cache_clear()
    captured_payload: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    llm_content,
                                    ensure_ascii=False,
                                )
                            }
                        }
                    ]
                },
                ensure_ascii=False,
            ).encode("utf-8")

    def fake_urlopen(request: object, timeout: int) -> FakeResponse:
        assert timeout == 60
        captured_payload.update(json.loads(request.data.decode("utf-8")))
        return FakeResponse()

    monkeypatch.setattr(
        "docchecker.services.rule_extractor.urllib.request.urlopen",
        fake_urlopen,
    )
    try:
        result = extract_rules_from_text(
            "中文摘要要求300字左右。",
            source_type=SourceType.requirement_doc,
        )
        return result, captured_payload
    finally:
        get_settings.cache_clear()
