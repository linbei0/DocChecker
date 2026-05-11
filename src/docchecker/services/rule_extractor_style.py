import re

from docchecker.domain.enums import RuleCategory, Severity, SourceType
from docchecker.domain.requirements import RequirementBlock
from docchecker.domain.rules import FormatRule
from docchecker.services.rule_extractor_factory import _rule
from docchecker.services.rule_extractor_types import RequirementChunk


def _extract_style_cluster_rules(
    blocks: list[RequirementBlock],
    source_type: SourceType,
) -> list[FormatRule]:
    clusters: dict[tuple[tuple[str, object], ...], list[RequirementBlock]] = {}
    for block in blocks:
        if block.type != "paragraph" or "正文段落" not in block.text:
            continue
        formatting = block.context.get("formatting")
        if not isinstance(formatting, dict):
            continue
        signature = tuple(
            sorted(
                (field, value)
                for field, value in formatting.items()
                if field
                in {
                    "fontFamilyEastAsia",
                    "fontSizePt",
                    "alignment",
                    "firstLineIndentCm",
                    "lineSpacing",
                    "spaceBeforePt",
                    "spaceAfterPt",
                }
            )
        )
        if signature:
            clusters.setdefault(signature, []).append(block)

    rules: list[FormatRule] = []
    for cluster_blocks in clusters.values():
        if len(cluster_blocks) < 2:
            continue
        formatting = cluster_blocks[0].context.get("formatting")
        if not isinstance(formatting, dict):
            continue
        chunk = RequirementChunk(
            text="；".join(block.text for block in cluster_blocks[:3]),
            location=",".join(block.location for block in cluster_blocks[:3]),
            target_hint="body.paragraph",
            evidence_type="style_cluster",
        )
        font_expectation = {
            field: formatting[field]
            for field in ["fontFamilyEastAsia", "fontSizePt"]
            if field in formatting
        }
        if font_expectation:
            rules.append(
                _rule(
                    "body_font",
                    RuleCategory.font,
                    "body.paragraph",
                    None,
                    font_expectation,
                    chunk,
                    source_type,
                    Severity.major,
                    confidence=0.82,
                )
            )
        paragraph_expectation = {
            field: formatting[field]
            for field in ["alignment", "firstLineIndentCm", "lineSpacing"]
            if field in formatting
        }
        if paragraph_expectation:
            rules.append(
                _rule(
                    "body_paragraph_from_style_cluster",
                    RuleCategory.paragraph,
                    "body.paragraph",
                    None,
                    paragraph_expectation,
                    chunk,
                    source_type,
                    Severity.major,
                    tolerance={"firstLineIndentCm": 0.15},
                    confidence=0.82,
                )
            )
    return rules


def _extract_exemplar_rules(
    blocks: list[RequirementBlock],
    source_type: SourceType,
) -> list[FormatRule]:
    rules: list[FormatRule] = []
    for block in blocks:
        if block.type != "paragraph" or _looks_like_toc_entry(block.text):
            continue
        level = _heading_exemplar_level(block.text)
        if level is None:
            continue
        formatting = block.context.get("formatting")
        if not isinstance(formatting, dict):
            continue
        chunk = RequirementChunk(text=block.text, location=block.location)
        scope = f"heading.{level}"
        selector = f"Heading {level}"
        heading_expectation = _heading_expectation_from_formatting(formatting)
        if heading_expectation:
            rules.append(
                _rule(
                    f"heading{level}_font",
                    RuleCategory.heading,
                    scope,
                    selector,
                    heading_expectation,
                    chunk,
                    source_type,
                    Severity.major,
                    confidence=0.98,
                )
            )
        paragraph_expectation = _paragraph_expectation_from_formatting(formatting)
        if "firstLineIndentCm" in paragraph_expectation:
            rules.append(
                _rule(
                    f"heading_{level}_first_line_indent",
                    RuleCategory.paragraph,
                    scope,
                    selector,
                    {"firstLineIndentCm": paragraph_expectation["firstLineIndentCm"]},
                    chunk,
                    source_type,
                    Severity.major,
                    confidence=0.98,
                )
            )
        if "alignment" in paragraph_expectation:
            rules.append(
                _rule(
                    f"heading_{level}_alignment",
                    RuleCategory.paragraph,
                    scope,
                    selector,
                    {"alignment": paragraph_expectation["alignment"]},
                    chunk,
                    source_type,
                    Severity.minor,
                    confidence=0.98,
                )
            )
        spacing = {
            field: paragraph_expectation[field]
            for field in ["spaceBeforePt", "spaceAfterPt"]
            if field in paragraph_expectation
        }
        if spacing:
            rules.append(
                _rule(
                    f"heading_{level}_paragraph_spacing",
                    RuleCategory.paragraph,
                    scope,
                    selector,
                    spacing,
                    chunk,
                    source_type,
                    Severity.minor,
                    confidence=0.98,
                )
            )
    return rules


def _heading_exemplar_level(text: str) -> int | None:
    match = re.match(r"^\s*(\d+(?:\.\d+){0,5})\s+\S+", text)
    if not match:
        return None
    return min(match.group(1).count(".") + 1, 6)


def _looks_like_toc_entry(text: str) -> bool:
    return bool(re.match(r"^\s*\d+(?:\.\d+){0,5}\s+.+\s+\d+\s*$", text))


def _heading_expectation_from_formatting(formatting: dict[str, object]) -> dict[str, object]:
    expectation: dict[str, object] = {}
    for field in ["fontFamilyEastAsia", "fontSizePt", "bold", "alignment"]:
        if field in formatting:
            expectation[field] = formatting[field]
    return expectation


def _paragraph_expectation_from_formatting(formatting: dict[str, object]) -> dict[str, object]:
    expectation: dict[str, object] = {}
    expectation["firstLineIndentCm"] = formatting.get("firstLineIndentCm", 0.0)
    expectation["spaceBeforePt"] = formatting.get("spaceBeforePt", 0.0)
    expectation["spaceAfterPt"] = formatting.get("spaceAfterPt", 0.0)
    expectation["alignment"] = formatting.get("alignment", "left")
    return expectation


