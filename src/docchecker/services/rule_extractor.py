import urllib.error
import urllib.request

from docchecker.core.config import get_settings
from docchecker.domain.enums import SourceType
from docchecker.domain.requirements import RequirementBlock, RequirementDocumentModel
from docchecker.domain.rules import (
    FormatRule,
    RuleExtractionIssue,
    RuleExtractionStats,
    RuleExtractionTrace,
)
from docchecker.services.rule_compiler import compile_rule_candidates
from docchecker.services.rule_extractor_llm import (
    _block_evidence_type,
    _block_target_hint,
    _blocks_from_chunks,
    _llm_rule_candidates,
)
from docchecker.services.rule_extractor_local import extract_local_rules
from docchecker.services.rule_extractor_quality import (
    _build_warnings,
    _dedupe_rules,
    _extract_unsupported_requirements,
    _move_conflicting_rules_to_confirmation,
    _split_requirement_chunks,
    _split_rules_by_confirmation,
    _summary,
)
from docchecker.services.rule_extractor_types import (
    RequirementChunk,
    RuleExtractionConfigurationError,
    RuleExtractionResult,
)

__all__ = [
    "RuleExtractionConfigurationError",
    "extract_rules_from_requirement_document",
    "extract_rules_from_text",
    "urllib",
]


def extract_rules_from_text(text: str, *, source_type: SourceType) -> RuleExtractionResult:
    chunks = _split_requirement_chunks(text)
    if not chunks:
        trace = RuleExtractionTrace(mode=get_settings().rule_extractor_mode)
        return RuleExtractionResult(
            rules=[],
            suggested_rules=[],
            parse_warnings=["规则来源文本为空，未生成候选规则。"],
            extraction_summary=_summary([], []),
            unsupported_requirements=[],
            extraction_trace=trace,
        )
    return _extract_rules_from_chunks(chunks, source_type=source_type)


def extract_rules_from_requirement_document(
    document: RequirementDocumentModel,
    *,
    source_type: SourceType,
) -> RuleExtractionResult:
    chunks = [
        RequirementChunk(
            text=block.text,
            location=block.location,
            target_hint=_block_target_hint(block),
            evidence_type=_block_evidence_type(block),
        )
        for block in document.blocks
        if block.text.strip()
    ]
    if not chunks:
        trace = RuleExtractionTrace(mode=get_settings().rule_extractor_mode)
        return RuleExtractionResult(
            rules=[],
            suggested_rules=[],
            parse_warnings=["规则来源文档没有可解析文本块，未生成候选规则。"],
            extraction_summary=_summary([], []),
            unsupported_requirements=[],
            extraction_trace=trace,
        )
    return _extract_rules_from_chunks(chunks, source_type=source_type, blocks=document.blocks)


def _extract_rules_from_chunks(
    chunks: list[RequirementChunk],
    *,
    source_type: SourceType,
    blocks: list[RequirementBlock] | None = None,
) -> RuleExtractionResult:
    settings = get_settings()
    local_extraction = extract_local_rules(chunks, source_type=source_type, blocks=blocks)
    local_candidates = local_extraction.candidates
    candidates = list(local_candidates)
    issues: list[RuleExtractionIssue] = []
    llm_candidate_count = 0
    llm_rejected_count = 0
    processed_block_count = len(blocks) if blocks is not None else len(chunks)
    batch_count = 1 if processed_block_count else 0
    if settings.rule_extractor_mode == "hybrid":
        llm_candidates, llm_issues, llm_stats = _llm_rule_candidates(
            blocks or _blocks_from_chunks(chunks)
        )
        candidates.extend(llm_candidates)
        issues.extend(llm_issues)
        llm_candidate_count = llm_stats.llm_candidate_count
        llm_rejected_count = llm_stats.llm_rejected_count
        processed_block_count = llm_stats.processed_block_count
        batch_count = llm_stats.batch_count

    compilation = compile_rule_candidates(candidates, source_type=source_type)
    combined_rules: list[FormatRule] = (
        local_extraction.rules + compilation.rules + compilation.suggested_rules
    )
    combined_rules, conflict_issues = _move_conflicting_rules_to_confirmation(combined_rules)
    auto_rules, suggested_rules = _split_rules_by_confirmation(combined_rules)
    issues.extend(compilation.issues)
    issues.extend(conflict_issues)
    deduped_rules = _dedupe_rules(auto_rules)
    deduped_suggested_rules = _dedupe_rules(suggested_rules)
    unsupported = _extract_unsupported_requirements(
        chunks,
        deduped_rules + deduped_suggested_rules,
        issues,
    )
    warnings = _build_warnings(
        chunks,
        deduped_rules,
        deduped_suggested_rules,
        unsupported,
    )
    conflict_count = len([issue for issue in conflict_issues if "冲突" in issue.message])
    stats = RuleExtractionStats(
        processed_block_count=processed_block_count,
        batch_count=batch_count,
        local_candidate_count=len(local_candidates),
        llm_candidate_count=llm_candidate_count,
        llm_rejected_count=llm_rejected_count,
        rejected_candidate_count=llm_rejected_count,
        unsupported_field_count=compilation.unsupported_field_count,
        conflict_count=conflict_count,
        auto_checkable_candidate_count=compilation.auto_checkable_candidate_count,
        needs_confirmation_candidate_count=compilation.needs_confirmation_candidate_count,
        unsupported_candidate_count=compilation.unsupported_candidate_count,
        auto_checkable_conversion_rate=round(
            len(deduped_rules) / (len(deduped_rules) + len(deduped_suggested_rules)),
            3,
        )
        if (len(deduped_rules) + len(deduped_suggested_rules))
        else 0,
    )
    trace = RuleExtractionTrace(
        mode=settings.rule_extractor_mode,
        candidates=candidates,
        issues=issues,
        stats=stats,
    )
    return RuleExtractionResult(
        rules=deduped_rules,
        suggested_rules=deduped_suggested_rules,
        parse_warnings=warnings,
        extraction_summary=_summary(
            deduped_rules,
            unsupported,
            chunks,
            suggested_rules=deduped_suggested_rules,
            issues=issues,
        ),
        unsupported_requirements=unsupported,
        extraction_trace=trace,
    )
