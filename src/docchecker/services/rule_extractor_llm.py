import json
import re

from pydantic import TypeAdapter, ValidationError

from docchecker.checkers.capabilities import capability_manifest
from docchecker.core.config import get_settings
from docchecker.domain.requirements import RequirementBlock
from docchecker.domain.rules import (
    ExtractedRuleCandidate,
    RuleExtractionIssue,
    RuleExtractionStats,
)
from docchecker.services.rule_extractor_style import _heading_exemplar_level
from docchecker.services.rule_extractor_targeting import (
    _has_explicit_non_body_target,
    _looks_like_body_format_requirement,
)
from docchecker.services.rule_extractor_types import (
    RequirementChunk,
    RuleExtractionConfigurationError,
)

LLM_REQUIREMENT_BLOCK_BATCH_SIZE = 80


def _urllib():
    from docchecker.services import rule_extractor

    return rule_extractor.urllib


def _llm_rule_candidates(
    blocks: list[RequirementBlock],
) -> tuple[list[ExtractedRuleCandidate], list[RuleExtractionIssue], RuleExtractionStats]:
    settings = get_settings()
    if not settings.llm_api_base or not settings.llm_api_key or not settings.llm_model:
        raise RuleExtractionConfigurationError(
            "DOC_CHECKER_RULE_EXTRACTOR_MODE=hybrid 时必须配置 "
            "DOC_CHECKER_LLM_API_BASE、DOC_CHECKER_LLM_API_KEY、DOC_CHECKER_LLM_MODEL。"
        )

    valid_candidates: list[ExtractedRuleCandidate] = []
    issues: list[RuleExtractionIssue] = []
    rejected_count = 0
    batches = list(_batched(blocks, LLM_REQUIREMENT_BLOCK_BATCH_SIZE))
    for batch_index, batch in enumerate(batches, start=1):
        payload = _llm_payload(settings.llm_model, batch)
        urllib_module = _urllib()
        request = urllib_module.request.Request(
            settings.llm_api_base.rstrip("/") + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib_module.request.urlopen(request, timeout=60) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except (urllib_module.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            issues.append(
                RuleExtractionIssue(
                    reason_code="invalid_llm_response",
                    message=f"LLM 规则抽取第 {batch_index} 批调用失败：{exc}",
                )
            )
            rejected_count += 1
            break

        content = response_payload["choices"][0]["message"]["content"]
        try:
            parsed = json.loads(content)
            candidates = TypeAdapter(list[ExtractedRuleCandidate]).validate_python(
                parsed.get("rule_candidates", [])
            )
        except (KeyError, TypeError, json.JSONDecodeError, ValidationError):
            issues.append(
                RuleExtractionIssue(
                    reason_code="invalid_llm_response",
                    message=(
                        f"LLM 返回的第 {batch_index} 批规则候选格式不符合系统 schema，"
                        "已拒绝本批候选；本地规则抽取结果仍可使用。"
                    ),
                    excerpt=str(content)[:300],
                )
            )
            rejected_count += 1
            continue
        for candidate in candidates:
            if candidate.evidence_span.strip():
                valid_candidates.append(candidate)
                continue
            rejected_count += 1
            issues.append(
                RuleExtractionIssue(
                    location=candidate.location,
                    category=candidate.category,
                    reason_code="ambiguous_requirement",
                    message="LLM 候选缺少原文证据，已拒绝映射为规则。",
                    excerpt=str(candidate.model_dump())[:300],
                )
            )
    return valid_candidates, issues, RuleExtractionStats(
        processed_block_count=len(blocks),
        batch_count=len(batches),
        llm_candidate_count=len(valid_candidates),
        llm_rejected_count=rejected_count,
        rejected_candidate_count=rejected_count,
    )


def _llm_payload(model: str, blocks: list[RequirementBlock]) -> dict[str, object]:
    return {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是论文格式规范抽取器。只从用户提供的规范块中抽取规则候选，"
                    "必须只返回 JSON 对象：{\"rule_candidates\": [...]}。"
                    "每条候选只能包含 category、target_scope、selector、expectation、"
                    "evidence_span、location、checkability、confidence、reason 字段。"
                    "category 只能是 page、font、paragraph、heading、header_footer、"
                    "caption、reference、structure、toc、abstract 之一，禁止自造类别。"
                    "checkability 只能是 checkable、needs_confirmation、unsupported 之一，"
                    "禁止使用 specific、vague 等其他值。"
                    "expectation 必须是 JSON object，不能是字符串；无法结构化时返回空对象。"
                    "evidence_span 必须逐字摘自用户提供的规范块，不得编造来源。"
                    "必须严格遵守随后用户消息中的 capability_manifest："
                    "只有 category、target_scope 和 expectation 字段都被 manifest 支持时，"
                    "才能返回 checkability=checkable；字段或范围不支持时必须返回 "
                    "checkability=unsupported 且 expectation={}，"
                    "不要把不支持项伪装为 needs_confirmation。"
                    "如需表达事实层或 OOXML 结构断言，只能使用 capability_manifest.rule_dsl "
                    "声明的 $dsl 形式。"
                    "示例：{\"rule_candidates\":[{\"category\":\"structure\","
                    "\"target_scope\":\"document.structure\",\"selector\":\"论文结构\","
                    "\"expectation\":{\"requiredSections\":[\"中文摘要\",\"正文\"]},"
                    "\"evidence_span\":\"中文摘要要求300字左右。\","
                    "\"location\":\"paragraph:42\","
                    "\"checkability\":\"needs_confirmation\","
                    "\"confidence\":0.8,"
                    "\"reason\":\"字数约束需要人工确认\"}]}"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "capability_manifest": capability_manifest(),
                        "requirement_blocks": [block.model_dump() for block in blocks],
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }


def _batched(
    blocks: list[RequirementBlock],
    size: int,
) -> list[list[RequirementBlock]]:
    return [blocks[index : index + size] for index in range(0, len(blocks), size)]


def _blocks_from_chunks(chunks: list[RequirementChunk]) -> list[RequirementBlock]:
    return [
        RequirementBlock(
            id=chunk.location or f"chunk:{index}",
            type="paragraph",
            location=chunk.location or f"chunk:{index}",
            text=chunk.text,
        )
        for index, chunk in enumerate(chunks, start=1)
    ]


def _block_target_hint(block: RequirementBlock) -> str | None:
    if block.type == "comment":
        nearby_text = str(block.context.get("nearby_text", ""))
        combined = f"{nearby_text} {block.text}"
        return _target_hint_from_text(combined)
    return _target_hint_from_text(block.text)


def _block_evidence_type(block: RequirementBlock) -> str:
    if block.type == "comment":
        return "comment_anchor" if block.context.get("nearby_location") else "explicit_text"
    if block.type == "table":
        return "table_cell"
    if block.type in {"header", "footer"}:
        return "explicit_text"
    if _heading_exemplar_level(block.text) is not None or _target_hint_from_text(block.text):
        return "exemplar_format"
    return "explicit_text"


def _target_hint_from_text(text: str) -> str | None:
    if "正文段落" in text or re.search(r"(^|[（(])正文([）)]|$)", text):
        return "body.paragraph"
    if not _has_explicit_non_body_target(text) and _looks_like_body_format_requirement(text):
        return "body.paragraph"
    return None
