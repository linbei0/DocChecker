import re

from docchecker.domain.enums import RuleCategory
from docchecker.domain.rules import (
    ExtractionSummary,
    FormatRule,
    RuleExtractionIssue,
    UnsupportedRequirement,
)
from docchecker.services.rule_extractor_types import RequirementChunk

ALL_RULE_CATEGORIES = list(RuleCategory)
UNSUPPORTED_CATEGORY_KEYWORDS = {
    RuleCategory.header_footer: ["页眉", "页脚"],
}
SUPPORTED_REQUIREMENT_KEYWORDS = [
    "正文",
    "行距",
    "首行缩进",
    "页边距",
    "一级标题",
    "二级标题",
    "三级标题",
    "论文题目",
    "中文论文题目",
    "学士学位论文",
    "摘要",
    "关键词",
    "段前",
    "段后",
    "A4",
]


def _split_rules_by_confirmation(
    rules: list[FormatRule],
) -> tuple[list[FormatRule], list[FormatRule]]:
    auto_rules: list[FormatRule] = []
    suggested_rules: list[FormatRule] = []
    for rule in rules:
        if rule.confidence >= 0.8 and rule.capability_status == "auto_checkable":
            auto_rules.append(rule)
            continue
        suggested_rules.append(
            rule.model_copy(
                update={
                    "enabled": False,
                    "capability_status": "conflict"
                    if rule.capability_status == "conflict"
                    else "needs_confirmation",
                    "confirmation_required": True,
                }
            )
        )
    return auto_rules, suggested_rules


def _move_conflicting_rules_to_confirmation(
    rules: list[FormatRule],
) -> tuple[list[FormatRule], list[RuleExtractionIssue]]:
    by_field: dict[tuple[str, str | None, RuleCategory, str], list[tuple[FormatRule, object]]] = {}
    conflict_keys: set[tuple[str, str | None, RuleCategory, str]] = set()
    auto_allowed: set[tuple[int, str, str | None, RuleCategory, str]] = set()
    issues: list[RuleExtractionIssue] = []
    for rule in rules:
        for field, value in rule.expectation.items():
            key = (rule.target.scope, rule.target.selector, rule.category, field)
            by_field.setdefault(key, []).append((rule, value))

    for key, values in by_field.items():
        distinct_values = []
        for _, value in values:
            if value not in distinct_values:
                distinct_values.append(value)
        if len(distinct_values) <= 1:
            continue
        conflict_keys.add(key)
        ranked = sorted(
            values,
            key=lambda item: _rule_conflict_rank(item[0]),
            reverse=True,
        )
        top_rank = _rule_conflict_rank(ranked[0][0])
        top_rules = [item for item in ranked if _rule_conflict_rank(item[0]) == top_rank]
        if len(top_rules) == 1:
            winner = top_rules[0][0]
            auto_allowed.add((id(winner), *key))
            message = (
                f"同一检查目标存在冲突规则：{key[3]} 存在多个值，"
                "已优先保留高置信/高优先级证据，其余规则需要人工确认。"
            )
            location = winner.source.location
            excerpt = winner.source.excerpt
        else:
            winner = ranked[0][0]
            message = (
                f"同一检查目标存在冲突规则：{key[3]} 存在多个同优先级值，"
                "需要人工确认。"
            )
            location = winner.source.location
            excerpt = winner.source.excerpt
        issues.append(
            RuleExtractionIssue(
                location=location,
                category=winner.category,
                reason_code="ambiguous_requirement",
                message=message,
                excerpt=excerpt,
            )
        )

    normalized_rules: list[FormatRule] = []
    for rule in rules:
        conflicting_fields = [
            field
            for field in rule.expectation
            if (rule.target.scope, rule.target.selector, rule.category, field) in conflict_keys
        ]
        rule_conflicts = bool(conflicting_fields)
        if not rule_conflicts:
            normalized_rules.append(rule)
            continue
        if all(
            (
                id(rule),
                rule.target.scope,
                rule.target.selector,
                rule.category,
                field,
            )
            in auto_allowed
            for field in conflicting_fields
        ):
            normalized_rules.append(rule)
            continue
        normalized_rules.append(
            rule.model_copy(
                update={
                    "enabled": False,
                    "capability_status": "conflict",
                    "confirmation_required": True,
                }
            )
        )
    return normalized_rules, issues


def _rule_conflict_rank(rule: FormatRule) -> tuple[int, float]:
    evidence_rank = {
        "template": 6,
        "exemplar_format": 5,
        "comment_anchor": 4,
        "style_cluster": 3,
        "table_cell": 2,
        "explicit_text": 1,
        "manual_text": 1,
        "llm_candidate": 1,
    }.get(rule.source.evidence_type, 0)
    return (evidence_rank, rule.confidence)


def _conflict_issues(rules: list[FormatRule]) -> list[RuleExtractionIssue]:
    by_field: dict[tuple[str, str | None, RuleCategory, str], FormatRule] = {}
    reported: set[tuple[str, str | None, RuleCategory, str]] = set()
    issues: list[RuleExtractionIssue] = []
    for rule in rules:
        for field, value in rule.expectation.items():
            key = (rule.target.scope, rule.target.selector, rule.category, field)
            existing = by_field.get(key)
            if existing is None:
                by_field[key] = rule
                continue
            existing_value = existing.expectation.get(field)
            if existing_value == value:
                continue
            if key in reported:
                continue
            reported.add(key)
            issues.append(
                RuleExtractionIssue(
                    location=rule.source.location,
                    category=rule.category,
                    reason_code="ambiguous_requirement",
                    message=(
                        f"同一检查目标存在冲突规则：{field} 同时为 "
                        f"{existing_value} 和 {value}，需要人工确认。"
                    ),
                    excerpt=rule.source.excerpt,
                )
            )
    return issues


def _extract_unsupported_requirements(
    chunks: list[RequirementChunk],
    rules: list[FormatRule],
    issues: list[RuleExtractionIssue] | None = None,
) -> list[UnsupportedRequirement]:
    unsupported: list[UnsupportedRequirement] = []
    rule_sources = {(rule.source.location, rule.source.excerpt) for rule in rules}
    for chunk in chunks:
        if (chunk.location, chunk.text[:300]) in rule_sources:
            continue
        for category, keywords in UNSUPPORTED_CATEGORY_KEYWORDS.items():
            if (
                category in {RuleCategory.header_footer}
                and _has_checkable_page_header_footer(chunk)
            ):
                continue
            if any(keyword in chunk.text for keyword in keywords):
                reason = (
                    f"已识别到 {category.value} 类要求，"
                    "但当前缺少对应检查器或结构化解析能力。"
                )
                unsupported.append(
                    UnsupportedRequirement(
                        category=category,
                        excerpt=chunk.text[:300],
                        location=chunk.location,
                        reason=reason,
                        reason_code="missing_checker",
                        target_scope=None,
                        capability_status="unsupported",
                    )
                )
                break
    for issue in issues or []:
        if issue.reason_code == "ambiguous_requirement" and _ambiguous_issue_covered_by_rule(
            issue,
            rules,
        ):
            continue
        if (
            issue.reason_code not in {"unsupported_field", "ambiguous_requirement"}
            and _issue_covered_by_rule(issue, rules)
        ):
            continue
        unsupported.append(
            UnsupportedRequirement(
                category=issue.category or RuleCategory.structure,
                excerpt=issue.excerpt or issue.message,
                location=issue.location,
                reason=issue.message,
                reason_code=issue.reason_code,
                target_scope=None,
                capability_status=(
                    "conflict"
                    if "冲突" in issue.message
                    else "needs_confirmation"
                    if issue.reason_code == "ambiguous_requirement"
                    else "unsupported"
                ),
            )
        )
    return _dedupe_unsupported(unsupported)


def _issue_covered_by_rule(
    issue: RuleExtractionIssue,
    rules: list[FormatRule],
) -> bool:
    if issue.category is None or issue.excerpt is None:
        return False
    return any(
        rule.category == issue.category and rule.source.excerpt == issue.excerpt[:300]
        for rule in rules
    )


def _ambiguous_issue_covered_by_rule(
    issue: RuleExtractionIssue,
    rules: list[FormatRule],
) -> bool:
    if issue.category is None:
        return False
    return any(
        rule.category == issue.category
        and (
            (issue.excerpt is not None and rule.source.excerpt == issue.excerpt[:300])
            or (
                issue.location is not None
                and rule.source.location == issue.location
            )
        )
        for rule in rules
    )


def _has_checkable_page_header_footer(chunk: RequirementChunk) -> bool:
    return bool(
        re.search(r"(页眉|页脚)\s*[0-9]+(?:\.[0-9]+)?\s*cm", chunk.text, re.I)
        or "页码" in chunk.text
        or re.search(r"页眉(?:内容)?[为是：:]\s*[^，。,；;\n]+", chunk.text)
    )


def _build_warnings(
    chunks: list[RequirementChunk],
    rules: list[FormatRule],
    suggested_rules: list[FormatRule],
    unsupported: list[UnsupportedRequirement],
) -> list[str]:
    warnings: list[str] = []
    if not rules:
        warnings.append("未识别到可自动校验的格式规则，请补充字体、字号、行距、缩进或页边距要求。")
    for item in unsupported:
        location = f"{item.location}：" if item.location else ""
        warnings.append(f"{location}{item.reason}")
    if suggested_rules:
        warnings.append(f"有 {len(suggested_rules)} 条规则需要人工确认后才会参与自动检查。")
    if not rules and not unsupported and chunks:
        warnings.append("规范文本已读取，但未命中当前规则能力矩阵中的格式要求。")
    return warnings


def _summary(
    rules: list[FormatRule],
    unsupported: list[UnsupportedRequirement],
    chunks: list[RequirementChunk] | None = None,
    *,
    suggested_rules: list[FormatRule] | None = None,
    issues: list[RuleExtractionIssue] | None = None,
) -> ExtractionSummary:
    suggested_rules = suggested_rules or []
    issues = issues or []
    supported_categories = sorted({rule.category for rule in rules}, key=lambda item: item.value)
    unsupported_categories = sorted(
        {item.category for item in unsupported},
        key=lambda item: item.value,
    )
    present_categories = set(supported_categories) | set(unsupported_categories)
    uncovered = sorted(set(ALL_RULE_CATEGORIES) - present_categories, key=lambda item: item.value)
    total_requirements = _count_requirement_candidates(
        chunks or [],
        rules + suggested_rules,
        unsupported,
    )
    handled = len(rules) + len(suggested_rules) + len(unsupported)
    return ExtractionSummary(
        total_requirements=total_requirements,
        structured_rules=len(rules),
        unsupported_requirements=len(unsupported),
        low_confidence_rules=len(suggested_rules),
        supported_categories=supported_categories,
        unsupported_categories=unsupported_categories,
        uncovered_categories=uncovered,
        auto_checkable_rules=len(rules),
        needs_confirmation_rules=len(suggested_rules),
        conflict_requirements=len([issue for issue in issues if "冲突" in issue.message]),
        coverage_rate=round(handled / total_requirements, 3) if total_requirements else 0,
    )


def _count_requirement_candidates(
    chunks: list[RequirementChunk],
    rules: list[FormatRule],
    unsupported: list[UnsupportedRequirement],
) -> int:
    if not chunks:
        return len(rules) + len(unsupported)
    count = 0
    for chunk in chunks:
        if any(keyword in chunk.text for keyword in SUPPORTED_REQUIREMENT_KEYWORDS):
            count += 1
            continue
        if any(
            keyword in chunk.text
            for keywords in UNSUPPORTED_CATEGORY_KEYWORDS.values()
            for keyword in keywords
        ):
            count += 1
    return max(count, len(rules) + len(unsupported))


def _split_requirement_chunks(text: str) -> list[RequirementChunk]:
    chunks: list[RequirementChunk] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        location, content = _parse_location_prefix(line)
        parts = [part.strip() for part in re.split(r"[。；;]", content) if part.strip()]
        if not parts:
            parts = [content]
        for part_index, part in enumerate(parts, start=1):
            part_location = location
            if location and len(parts) > 1:
                part_location = f"{location},part:{part_index}"
            chunks.append(
                RequirementChunk(
                    text=part,
                    location=part_location,
                    evidence_type="manual_text",
                )
            )
    if not chunks:
        normalized = re.sub(r"\s+", " ", text.strip())
        chunks.extend(
            RequirementChunk(text=part.strip(), evidence_type="manual_text")
            for part in re.split(r"[。；;\n\r]", normalized)
            if part.strip()
        )
    return chunks


def _parse_location_prefix(line: str) -> tuple[str | None, str]:
    match = re.match(r"^((?:paragraph|table|comment):[^\t]+)\t(.+)$", line)
    if not match:
        return None, line
    return match.group(1), match.group(2).strip()


def _dedupe_rules(rules: list[FormatRule]) -> list[FormatRule]:
    by_id: dict[str, FormatRule] = {}
    order: list[str] = []
    for rule in rules:
        existing = by_id.get(rule.id)
        if existing is None:
            by_id[rule.id] = rule
            order.append(rule.id)
            continue
        by_id[rule.id] = _merge_rule(existing, rule)
    return [by_id[rule_id] for rule_id in order]


def _merge_rule(existing: FormatRule, incoming: FormatRule) -> FormatRule:
    expectation = dict(existing.expectation)
    for field, value in incoming.expectation.items():
        if field not in expectation or incoming.confidence > existing.confidence:
            expectation[field] = value
    confidence = max(existing.confidence, incoming.confidence)
    source = incoming.source if incoming.confidence > existing.confidence else existing.source
    return existing.model_copy(
        update={
            "expectation": expectation,
            "confidence": confidence,
            "source": source,
        }
    )


def _dedupe_unsupported(items: list[UnsupportedRequirement]) -> list[UnsupportedRequirement]:
    seen: set[tuple[RuleCategory, str | None, str]] = set()
    deduped: list[UnsupportedRequirement] = []
    for item in items:
        key = (item.category, item.location, item.excerpt)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
