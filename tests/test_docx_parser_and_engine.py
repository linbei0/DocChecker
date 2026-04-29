from pathlib import Path

import pytest
from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
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


def test_parse_docx_resolves_style_inherited_paragraph_format(tmp_path: Path) -> None:
    path = tmp_path / "styled.docx"
    document = Document()
    style = document.styles["Normal"]
    style.font.name = "宋体"
    style.font.size = Pt(12)
    style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
    style.paragraph_format.space_after = Pt(6)
    document.add_paragraph("结论")
    document.save(path)

    model = parse_docx(path, document_id="doc_1", source_filename="styled.docx")
    paragraph = model.paragraphs[0]

    assert paragraph.font_family == "宋体"
    assert paragraph.font_size_pt == 12
    assert paragraph.alignment == "left"
    assert paragraph.space_after_pt == 6


def test_parse_docx_resolves_east_asia_font_from_style_xml(tmp_path: Path) -> None:
    path = tmp_path / "heading-font.docx"
    document = Document()
    style = document.styles["Heading 1"]
    r_pr = style._element.get_or_add_rPr()
    r_fonts = r_pr.get_or_add_rFonts()
    r_fonts.set(qn("w:eastAsia"), "黑体")
    style.font.size = Pt(16)
    document.add_paragraph("绪论", style="Heading 1")
    document.save(path)

    model = parse_docx(path, document_id="doc_1", source_filename="heading-font.docx")
    paragraph = model.paragraphs[0]

    assert paragraph.font_family == "黑体"
    assert paragraph.font_size_pt == 16


def test_parse_docx_tracks_mixed_script_fonts_separately(tmp_path: Path) -> None:
    path = tmp_path / "mixed-font.docx"
    document = Document()
    paragraph = document.add_paragraph()
    chinese = paragraph.add_run("关键词：校园社团管理")
    chinese._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "宋体")
    english = paragraph.add_run(" Layui SpringBoot")
    english.font.name = "Times New Roman"
    document.save(path)

    model = parse_docx(path, document_id="doc_1", source_filename="mixed-font.docx")
    paragraph_node = model.paragraphs[0]

    assert paragraph_node.font_family is None
    assert paragraph_node.font_family_east_asia == "宋体"
    assert paragraph_node.font_family_ascii == "Times New Roman"
    assert [run.script for run in paragraph_node.runs] == ["east_asia", "ascii"]
    assert paragraph_node.runs[0].font_family_east_asia == "宋体"
    assert paragraph_node.runs[1].font_family_ascii == "Times New Roman"


def test_font_checker_reports_mixed_east_asia_fonts_instead_of_unparsed(
    tmp_path: Path,
) -> None:
    path = tmp_path / "mixed-font-check.docx"
    document = Document()
    paragraph = document.add_paragraph()
    label = paragraph.add_run("关键词：")
    label._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "黑体")
    content = paragraph.add_run("校园社团管理")
    content._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "宋体")
    english = paragraph.add_run(" Layui")
    english.font.name = "Times New Roman"
    document.save(path)
    model = parse_docx(path, document_id="doc_1", source_filename="mixed-font-check.docx")
    ruleset = RuleSet(
        id="ruleset_mixed_font",
        name="混排字体",
        source_type=SourceType.manual,
        version="1.0.0",
        created_at="2026-04-26T00:00:00+08:00",
        rules=[
            FormatRule(
                id="keyword_cn_font",
                category=RuleCategory.font,
                target=RuleTarget(scope="keywords.paragraph", selector="关键词"),
                expectation={"fontFamilyEastAsia": "宋体"},
                severity=Severity.major,
                source=RuleSource(type=SourceType.manual, excerpt="关键词宋体"),
                confidence=1,
            )
        ],
    )

    findings = CheckEngine().run(model, ruleset.rules)

    assert len(findings) == 1
    assert findings[0].actual == {"fontFamilyEastAsia": "混合：黑体、宋体"}
    assert findings[0].certainty.value == "certain"


def test_parse_docx_tracks_nearest_heading_as_logical_section(tmp_path: Path) -> None:
    path = tmp_path / "sample.docx"
    document = Document()
    document.add_heading("绪论", level=1)
    document.add_paragraph("研究背景")
    document.save(path)

    model = parse_docx(path, document_id="doc_1", source_filename="sample.docx")

    assert model.paragraphs[0].raw["section_name"] == "绪论"
    assert model.paragraphs[1].raw["section_name"] == "绪论"
    assert model.logical_sections[0].role == "body"
    assert model.logical_sections[0].start_paragraph_index == 0


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


def test_heading_rules_do_not_match_body_text_mentions(tmp_path: Path) -> None:
    path = tmp_path / "heading-selector.docx"
    document = Document()
    document.add_heading("绪论", level=1)
    document.add_paragraph("第一章：绪论。本章介绍研究背景。")
    document.save(path)
    model = parse_docx(path, document_id="doc_1", source_filename="heading-selector.docx")
    ruleset = RuleSet(
        id="ruleset_heading",
        name="标题规则",
        source_type=SourceType.manual,
        version="1.0.0",
        created_at="2026-04-26T00:00:00+08:00",
        rules=[
            FormatRule(
                id="heading_alignment",
                category=RuleCategory.heading,
                target=RuleTarget(scope="heading.level1", selector="绪论"),
                expectation={"alignment": "left"},
                severity=Severity.major,
                source=RuleSource(type=SourceType.manual, excerpt="一级标题左对齐"),
                confidence=1,
            )
        ],
    )

    findings = CheckEngine().run(model, ruleset.rules)

    assert len(findings) == 1
    assert findings[0].excerpt == "绪论"


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


def test_semantic_checkers_report_structure_and_reference_findings(tmp_path: Path) -> None:
    path = tmp_path / "paper.docx"
    document = Document()
    document.add_paragraph("摘要")
    document.add_paragraph("正文内容")
    document.add_paragraph("[2] 不连续编号参考文献")
    document.save(path)
    model = parse_docx(path, document_id="doc_1", source_filename="paper.docx")
    ruleset = RuleSet(
        id="ruleset_semantic",
        name="语义规则",
        source_type=SourceType.manual,
        version="1.0.0",
        created_at="2026-04-26T00:00:00+08:00",
        rules=[
            FormatRule(
                id="structure_required_sections",
                category=RuleCategory.structure,
                target=RuleTarget(scope="document.structure", selector="论文结构"),
                expectation={"requiredSections": ["摘要", "目录", "正文"]},
                severity=Severity.major,
                source=RuleSource(type=SourceType.manual, excerpt="论文应包含摘要、目录、正文"),
                confidence=1,
            ),
            FormatRule(
                id="reference_basic_entries",
                category=RuleCategory.reference,
                target=RuleTarget(scope="document.references", selector="参考文献"),
                expectation={"requiresReferences": True, "numbering": "bracketed"},
                severity=Severity.minor,
                source=RuleSource(type=SourceType.manual, excerpt="参考文献按编号排列"),
                confidence=1,
            ),
        ],
    )

    findings = CheckEngine().run(model, ruleset.rules)
    rule_ids = {finding.rule_id for finding in findings}

    assert "structure_required_sections" in rule_ids
    assert "reference_basic_entries" in rule_ids


def test_structure_checker_matches_common_section_aliases(tmp_path: Path) -> None:
    path = tmp_path / "paper-alias.docx"
    document = Document()
    document.add_paragraph("摘 要：系统设计与实现。")
    document.add_paragraph("关键词：校园社团管理；Layui")
    document.add_paragraph("目  录")
    document.add_heading("绪论", level=1)
    document.add_paragraph("正文内容")
    document.save(path)
    model = parse_docx(path, document_id="doc_1", source_filename="paper-alias.docx")
    ruleset = RuleSet(
        id="ruleset_structure_alias",
        name="结构规则",
        source_type=SourceType.manual,
        version="1.0.0",
        created_at="2026-04-26T00:00:00+08:00",
        rules=[
            FormatRule(
                id="structure_required_sections",
                category=RuleCategory.structure,
                target=RuleTarget(scope="document.structure", selector="论文结构"),
                expectation={
                    "requiredSections": ["中文摘要", "中文关键词", "目录", "正文"]
                },
                severity=Severity.major,
                source=RuleSource(type=SourceType.manual, excerpt="论文结构要求"),
                confidence=1,
            )
        ],
    )

    findings = CheckEngine().run(model, ruleset.rules)

    assert findings == []


def test_structure_checker_ignores_toc_entries_for_order(tmp_path: Path) -> None:
    path = tmp_path / "paper-toc-order.docx"
    document = Document()
    document.add_paragraph("摘 要：系统设计与实现。")
    document.add_paragraph("关键词：校园社团管理；Layui")
    document.add_paragraph("目  录")
    document.styles.add_style("toc 1", WD_STYLE_TYPE.PARAGRAPH)
    document.add_paragraph("致  谢\t55", style="toc 1")
    document.add_heading("绪论", level=1)
    document.add_paragraph("正文内容")
    document.add_paragraph("致  谢")
    document.add_paragraph("参考文献")
    document.save(path)
    model = parse_docx(path, document_id="doc_1", source_filename="paper-toc-order.docx")
    roles = [section.role for section in model.logical_sections]
    assert roles == [
        "abstract",
        "keywords",
        "toc",
        "body",
        "acknowledgements",
        "references",
    ]
    ruleset = RuleSet(
        id="ruleset_structure_order",
        name="结构顺序规则",
        source_type=SourceType.manual,
        version="1.0.0",
        created_at="2026-04-26T00:00:00+08:00",
        rules=[
            FormatRule(
                id="structure_required_sections",
                category=RuleCategory.structure,
                target=RuleTarget(scope="document.structure", selector="论文结构"),
                expectation={
                    "requiredSections": [
                        "中文摘要",
                        "中文关键词",
                        "目录",
                        "正文",
                        "致谢",
                        "参考文献",
                    ]
                },
                severity=Severity.major,
                source=RuleSource(type=SourceType.manual, excerpt="论文结构要求"),
                confidence=1,
            )
        ],
    )

    findings = CheckEngine().run(model, ruleset.rules)

    assert findings == []


def test_structure_finding_includes_document_excerpt(tmp_path: Path) -> None:
    path = tmp_path / "paper-missing.docx"
    document = Document()
    document.add_heading("绪论", level=1)
    document.add_paragraph("正文内容")
    document.save(path)
    model = parse_docx(path, document_id="doc_1", source_filename="paper-missing.docx")
    ruleset = RuleSet(
        id="ruleset_structure_missing",
        name="结构规则",
        source_type=SourceType.manual,
        version="1.0.0",
        created_at="2026-04-26T00:00:00+08:00",
        rules=[
            FormatRule(
                id="structure_required_sections",
                category=RuleCategory.structure,
                target=RuleTarget(scope="document.structure", selector="论文结构"),
                expectation={"requiredSections": ["中文摘要", "中文关键词", "目录", "正文"]},
                severity=Severity.major,
                source=RuleSource(type=SourceType.manual, excerpt="论文结构要求"),
                confidence=1,
            )
        ],
    )

    findings = CheckEngine().run(model, ruleset.rules)

    assert len(findings) == 1
    assert findings[0].excerpt is not None
    assert "绪论" in findings[0].excerpt
