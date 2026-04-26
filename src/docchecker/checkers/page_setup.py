from docchecker.checkers.base import relevant_rules
from docchecker.domain.document import DocumentModel
from docchecker.domain.enums import Certainty, RuleCategory
from docchecker.domain.findings import CheckFinding, FindingLocation
from docchecker.domain.rules import FormatRule


class PageSetupChecker:
    checker_id = "page_setup_checker"
    supported_categories = {RuleCategory.page}

    def check(self, document: DocumentModel, rules: list[FormatRule]) -> list[CheckFinding]:
        findings: list[CheckFinding] = []
        for rule in relevant_rules(rules, self.supported_categories):
            for section in document.sections:
                for field, expected in rule.expectation.items():
                    actual = getattr(section, field, None)
                    if actual is None:
                        findings.append(
                            self._finding(
                                rule, section.index, field, expected, actual, Certainty.unknown
                            )
                        )
                    elif not _within_tolerance(actual, expected, rule.tolerance.get(field, 0)):
                        findings.append(self._finding(rule, section.index, field, expected, actual))
        return findings

    def _finding(
        self,
        rule: FormatRule,
        section_index: int,
        field: str,
        expected,
        actual,
        certainty: Certainty = Certainty.certain,
    ) -> CheckFinding:
        return CheckFinding(
            id=f"{rule.id}:section-{section_index}:{field}",
            rule_id=rule.id,
            checker_id=self.checker_id,
            severity=rule.severity,
            location=FindingLocation(area=f"section:{section_index}"),
            expected={field: expected},
            actual={field: actual},
            evidence=f"第 {section_index + 1} 节页面设置字段 {field} 与规则不一致。",
            suggestion="请在 Word 页面设置中调整对应纸张、页边距或页眉页脚距离。",
            certainty=certainty,
        )


def _within_tolerance(actual: float, expected: float, tolerance: float) -> bool:
    return abs(actual - expected) <= tolerance
