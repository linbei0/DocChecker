from pathlib import Path

import pytest
from docx import Document
from docx.shared import Cm, Pt

from docchecker.checkers.engine import CheckEngine
from docchecker.domain.enums import RuleCategory, Severity, SourceType
from docchecker.domain.findings import CheckReport
from docchecker.domain.rules import FormatRule, RuleSet, RuleSource, RuleTarget
from docchecker.parsing.docx_parser import parse_docx
from docchecker.reports.markdown import render_markdown_report
from docchecker.services.docx_validator import validate_docx_path


def _create_docx(path: Path) -> None:
    document = Document()
    section = document.sections[0]
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)
    paragraph = document.add_paragraph("正文内容")
    run = paragraph.runs[0]
    run.font.name = "Arial"
    run.font.size = Pt(12)
    document.save(path)


def test_parse_docx_reads_sections_and_paragraphs(tmp_path: Path) -> None:
    path = tmp_path / "sample.docx"
    _create_docx(path)

    validate_docx_path(path, max_size_bytes=1024 * 1024)
    model = parse_docx(path, document_id="doc_1", source_filename="sample.docx")

    assert model.sections[0].margin_top_cm == pytest.approx(2.5, abs=0.01)
    assert model.paragraphs[0].text == "正文内容"
    assert model.paragraphs[0].font_size_pt == 12


def test_parse_docx_tracks_nearest_heading_as_logical_section(tmp_path: Path) -> None:
    path = tmp_path / "sample.docx"
    document = Document()
    document.add_heading("绪论", level=1)
    document.add_paragraph("研究背景")
    document.save(path)

    model = parse_docx(path, document_id="doc_1", source_filename="sample.docx")

    assert model.paragraphs[0].raw["section_name"] == "绪论"
    assert model.paragraphs[1].raw["section_name"] == "绪论"


def test_engine_reports_font_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "sample.docx"
    _create_docx(path)
    model = parse_docx(path, document_id="doc_1", source_filename="sample.docx")
    ruleset = RuleSet(
        id="ruleset_test",
        name="测试规则",
        source_type=SourceType.manual,
        version="1.0.0",
        created_at="2026-04-26T00:00:00+08:00",
        rules=[
            FormatRule(
                id="body_font_family",
                category=RuleCategory.font,
                target=RuleTarget(scope="body.paragraph"),
                expectation={"fontFamilyEastAsia": "宋体"},
                severity=Severity.major,
                source=RuleSource(type=SourceType.manual, excerpt="正文宋体"),
                confidence=1,
            )
        ],
    )

    findings = CheckEngine().run(model, ruleset.rules)

    assert len(findings) == 1
    assert findings[0].rule_id == "body_font_family"
    assert findings[0].actual == {"fontFamilyEastAsia": "Arial"}
    assert findings[0].excerpt == "正文内容"
    assert findings[0].location.paragraph_number == 1
    assert findings[0].location.display_path == "第 1 段"
    assert findings[0].context["style_name"] == "Normal"
    assert findings[0].context["field_label"] == "中文字体"


def test_markdown_report_includes_fragment_context(tmp_path: Path) -> None:
    path = tmp_path / "sample.docx"
    _create_docx(path)
    model = parse_docx(path, document_id="doc_1", source_filename="sample.docx")
    ruleset = RuleSet(
        id="ruleset_test",
        name="测试规则",
        source_type=SourceType.manual,
        version="1.0.0",
        created_at="2026-04-26T00:00:00+08:00",
        rules=[
            FormatRule(
                id="body_font_family",
                category=RuleCategory.font,
                target=RuleTarget(scope="body.paragraph"),
                expectation={"fontFamilyEastAsia": "宋体"},
                severity=Severity.major,
                source=RuleSource(type=SourceType.manual, excerpt="正文宋体"),
                confidence=1,
            )
        ],
    )
    findings = CheckEngine().run(model, ruleset.rules)
    report = CheckReport(
        id="report_test",
        document_id="doc_1",
        ruleset_id=ruleset.id,
        checker_version="0.1.0",
        generated_at="2026-04-26T00:00:00+08:00",
        findings=findings,
    )

    content = render_markdown_report(report)

    assert "## 问题片段" in content
    assert "第 1 段" in content
    assert "正文内容" in content
    assert "期望值：fontFamilyEastAsia=宋体" in content
    assert "实际值：fontFamilyEastAsia=Arial" in content
