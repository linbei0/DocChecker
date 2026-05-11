import re

from docchecker.domain.enums import RuleCategory
from docchecker.domain.rules import ExtractedRuleCandidate
from docchecker.services.rule_extractor_types import RequirementChunk


def _local_rule_candidates(chunks: list[RequirementChunk]) -> list[ExtractedRuleCandidate]:
    candidates: list[ExtractedRuleCandidate] = []
    candidates.extend(_structure_candidates(chunks))
    candidates.extend(_toc_candidates(chunks))
    candidates.extend(_caption_candidates(chunks))
    candidates.extend(_reference_candidates(chunks))
    candidates.extend(_header_footer_candidates(chunks))
    candidates.extend(_abstract_candidates(chunks))
    return candidates


def _structure_candidates(chunks: list[RequirementChunk]) -> list[ExtractedRuleCandidate]:
    section_names = [
        "封面",
        "诚信声明",
        "版权声明",
        "中文摘要",
        "中文关键词",
        "英文摘要",
        "英文关键词",
        "目录",
        "正文",
        "致谢",
        "参考文献",
    ]
    matched: list[str] = []
    evidence: list[str] = []
    locations: list[str] = []
    for chunk in chunks:
        for name in section_names:
            if name in chunk.text and name not in matched:
                matched.append(name)
                evidence.append(chunk.text)
                if chunk.location:
                    locations.append(chunk.location)
    if len(matched) < 2:
        return []
    ordered = [name for name in section_names if name in matched]
    return [
        ExtractedRuleCandidate(
            category=RuleCategory.structure,
            target_scope="document.structure",
            selector="论文结构",
            expectation={"requiredSections": ordered},
            evidence_span="；".join(evidence[:4]),
            location=",".join(locations[:4]) if locations else None,
            checkability="checkable",
            confidence=0.82,
        )
    ]


def _toc_candidates(chunks: list[RequirementChunk]) -> list[ExtractedRuleCandidate]:
    for chunk in chunks:
        if "目录" in chunk.text or "目次" in chunk.text:
            return [
                ExtractedRuleCandidate(
                    category=RuleCategory.toc,
                    target_scope="document.toc",
                    selector="目录",
                    expectation={"requiresToc": True, "requiresEntries": True},
                    evidence_span=chunk.text,
                    location=chunk.location,
                    checkability="checkable",
                    confidence=0.84,
                )
            ]
    return []


def _caption_candidates(chunks: list[RequirementChunk]) -> list[ExtractedRuleCandidate]:
    for chunk in chunks:
        if any(keyword in chunk.text for keyword in ["图题", "表题", "题注", "图注", "表注"]):
            return [
                ExtractedRuleCandidate(
                    category=RuleCategory.caption,
                    target_scope="document.caption",
                    selector="图题和表题",
                    expectation={"captionPattern": "图1.1 题名 / 表1.1 题名"},
                    evidence_span=chunk.text,
                    location=chunk.location,
                    checkability="checkable",
                    confidence=0.8,
                )
            ]
    return []


def _reference_candidates(chunks: list[RequirementChunk]) -> list[ExtractedRuleCandidate]:
    for chunk in chunks:
        if _is_reference_requirement(chunk.text):
            return [
                ExtractedRuleCandidate(
                    category=RuleCategory.reference,
                    target_scope="document.references",
                    selector="参考文献",
                    expectation={"requiresReferences": True, "numbering": "bracketed"},
                    evidence_span=chunk.text,
                    location=chunk.location,
                    checkability="checkable",
                    confidence=0.82,
                )
            ]
    return []


def _is_reference_requirement(text: str) -> bool:
    if re.search(r"(不|避免|禁止|无需|不得).{0,8}(引用|参考文献)", text):
        return False
    return bool(
        "参考文献" in text
        and re.search(r"(著录|编排|格式|编号|顺序|GB/T|列出|不少于)", text, re.I)
    )


def _header_footer_candidates(chunks: list[RequirementChunk]) -> list[ExtractedRuleCandidate]:
    candidates: list[ExtractedRuleCandidate] = []
    for chunk in chunks:
        if "页眉" not in chunk.text and "页脚" not in chunk.text and "页码" not in chunk.text:
            continue
        expectation: dict[str, object] = {}
        if "页码" in chunk.text:
            expectation["requiresPageNumber"] = True
        text_match = re.search(r"页眉(?:内容)?[为是：:]\s*([^，。,；;\n]+)", chunk.text)
        if text_match:
            expectation["textContains"] = text_match.group(1).strip()
        if not expectation:
            continue
        candidates.append(
            ExtractedRuleCandidate(
                category=RuleCategory.header_footer,
                target_scope="document.header_footer",
                selector="页眉页脚",
                expectation=expectation,
                evidence_span=chunk.text,
                location=chunk.location,
                checkability="checkable",
                confidence=0.82,
            )
        )
    return candidates


def _abstract_candidates(chunks: list[RequirementChunk]) -> list[ExtractedRuleCandidate]:
    candidates: list[ExtractedRuleCandidate] = []
    for chunk in chunks:
        lower_text = chunk.text.lower()
        if (
            "摘要" not in chunk.text
            and "abstract" not in lower_text
            and "关键词" not in chunk.text
            and "keywords" not in lower_text
        ):
            continue
        expectation: dict[str, object] = {}
        if _requires_abstract_presence(chunk.text, ("中文摘要", "摘要")):
            expectation["requiresChineseAbstract"] = True
        if _requires_abstract_presence(chunk.text, ("英文摘要", "Abstract")):
            expectation["requiresEnglishAbstract"] = True
        if _requires_abstract_presence(chunk.text, ("关键词", "Keywords")):
            expectation["requiresKeywords"] = True
        min_count = _word_count_requirement(chunk.text, minimum=True)
        max_count = _word_count_requirement(chunk.text, minimum=False)
        if min_count is not None:
            expectation["minWordCount"] = min_count
        if max_count is not None:
            expectation["maxWordCount"] = max_count
        if not expectation:
            continue
        candidates.append(
            ExtractedRuleCandidate(
                category=RuleCategory.abstract,
                target_scope="document.abstract",
                selector="摘要",
                expectation=expectation,
                evidence_span=chunk.text,
                location=chunk.location,
                checkability="checkable",
                confidence=0.82,
            )
        )
    return candidates


def _requires_abstract_presence(text: str, names: tuple[str, ...]) -> bool:
    for name in names:
        escaped = re.escape(name)
        if re.search(rf"(?:应|须|必须|需|需要|包括|包含).{{0,20}}{escaped}", text, flags=re.I):
            return True
        if re.search(rf"{escaped}.{{0,12}}(?:应包括|应包含|须包括|须包含|必备)", text, flags=re.I):
            return True
    return False


def _word_count_requirement(text: str, *, minimum: bool) -> int | None:
    if minimum:
        pattern = r"(?:不少于|至少|不低于)\s*(\d+)\s*[字词]?"
    else:
        pattern = r"(?:不超过|不多于|少于|以内)\s*(\d+)\s*[字词]?"
    match = re.search(pattern, text)
    return int(match.group(1)) if match else None

