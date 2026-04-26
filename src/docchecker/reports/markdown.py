from collections import Counter

from docchecker.domain.findings import CheckReport


def render_markdown_report(report: CheckReport) -> str:
    severity_counts = Counter(finding.severity for finding in report.findings)
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
    if report.parse_warnings:
        lines.extend(["", "## 解析警告", ""])
        for warning in report.parse_warnings:
            lines.append(f"- {warning}")
    lines.extend(["", "## 问题清单", ""])
    for finding in report.findings:
        lines.extend(
            [
                f"### {finding.id}",
                "",
                f"- 严重程度：{finding.severity}",
                f"- 规则 ID：{finding.rule_id}",
                f"- 检查器：{finding.checker_id}",
                f"- 位置：{finding.location.model_dump(exclude_none=True)}",
                f"- 期望：{finding.expected}",
                f"- 实际：{finding.actual}",
                f"- 证据：{finding.evidence}",
                f"- 建议：{finding.suggestion}",
                f"- 确定性：{finding.certainty}",
                "",
            ]
        )
    return "\n".join(lines)
