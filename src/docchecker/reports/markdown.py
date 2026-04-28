from collections import Counter
from typing import Any

from docchecker.domain.findings import CheckFinding, CheckReport


def render_markdown_report(report: CheckReport) -> str:
    severity_counts = Counter(finding.severity for finding in report.findings)
    category_counts = Counter(finding.category or "未分类" for finding in report.findings)
    lines = [
        "# 论文格式检查报告",
        "",
        f"- 报告 ID：{report.id}",
        f"- 文档 ID：{report.document_id}",
        f"- 规则集 ID：{report.ruleset_id}",
        f"- 检查器版本：{report.checker_version}",
        f"- 生成时间：{report.generated_at}",
        "",
        "## 总览",
        "",
        f"- 问题总数：{len(report.findings)}",
    ]
    for severity, count in sorted(severity_counts.items()):
        lines.append(f"- {severity}：{count}")
    lines.extend(["", "## 问题分布", ""])
    for category, count in sorted(category_counts.items()):
        lines.append(f"- {category}：{count}")
    if report.parse_warnings:
        lines.extend(["", "## 解析警告", ""])
        for warning in report.parse_warnings:
            lines.append(f"- {warning}")
    lines.extend(["", "## 问题片段", ""])
    for group_title, findings in _group_findings(report.findings).items():
        lines.extend([f"### {group_title}", ""])
        excerpt = findings[0].excerpt
        if excerpt:
            lines.extend([f"> {excerpt}", ""])
        for finding in findings:
            field_label = finding.context.get("field_label") or finding.rule_id
            lines.extend(
                [
                    f"#### {field_label}",
                    "",
                    f"- 严重程度：{finding.severity}",
                    f"- 规则 ID：{finding.rule_id}",
                    f"- 检查器：{finding.checker_id}",
                    f"- 位置：{_format_location(finding)}",
                    f"- 期望值：{_format_mapping(finding.expected)}",
                    f"- 实际值：{_format_mapping(finding.actual)}",
                    f"- 证据：{finding.evidence}",
                    f"- 建议：{finding.suggestion}",
                    f"- 确定性：{finding.certainty}",
                    "",
                ]
            )
    return "\n".join(lines)


def _group_findings(findings: list[CheckFinding]) -> dict[str, list[CheckFinding]]:
    groups: dict[str, list[CheckFinding]] = {}
    for finding in findings:
        title = _format_location(finding)
        groups.setdefault(title, []).append(finding)
    return groups


def _format_location(finding: CheckFinding) -> str:
    if finding.location.display_path:
        return finding.location.display_path
    if finding.location.paragraph_number is not None:
        return f"第 {finding.location.paragraph_number} 段"
    if finding.location.paragraph_index is not None:
        return f"第 {finding.location.paragraph_index + 1} 段"
    location = finding.location.model_dump(exclude_none=True)
    return str(location) if location else "未定位"


def _format_mapping(values: dict[str, Any]) -> str:
    if not values:
        return "-"
    return "，".join(f"{key}={_format_value(value)}" for key, value in values.items())


def _format_value(value: Any) -> str:
    if value is None:
        return "未解析"
    if isinstance(value, bool):
        return "是" if value else "否"
    return str(value)
