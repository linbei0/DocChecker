import re
from collections.abc import Iterable
from typing import Any

from docchecker.domain.document import DocumentModel
from docchecker.domain.enums import RuleCategory
from docchecker.domain.findings import CheckFinding, FindingLocation
from docchecker.domain.rules import FormatRule


class PropertyChecker:
    checker_id = "property"
    supported_categories = set(RuleCategory)

    def check(self, document: DocumentModel, rules: list[FormatRule]) -> list[CheckFinding]:
        findings: list[CheckFinding] = []
        for rule in rules:
            if (
                not rule.enabled
                or rule.capability_status != "auto_checkable"
                or rule.confirmation_required
            ):
                continue
            assertions = rule.expectation.get("$facts")
            if not isinstance(assertions, list):
                continue
            for index, assertion in enumerate(assertions):
                if not isinstance(assertion, dict):
                    continue
                if not _assertion_passes(document, assertion):
                    findings.append(_finding(rule, assertion, index, document))
        return findings


def _assertion_passes(document: DocumentModel, assertion: dict[str, Any]) -> bool:
    path = assertion.get("path")
    operator = assertion.get("operator")
    if not isinstance(path, str) or not isinstance(operator, str):
        return False
    values = _values_at_path(document, path)
    expected = assertion.get("value")
    if operator == "exists":
        return any(_present(value) for value in values)
    if operator == "equals":
        return any(value == expected for value in values)
    if operator == "contains":
        return any(isinstance(value, str) and str(expected) in value for value in values)
    if operator == "matches":
        return any(isinstance(value, str) and re.search(str(expected), value) for value in values)
    if operator == "range":
        minimum = assertion.get("min")
        maximum = assertion.get("max")
        return any(_in_range(value, minimum, maximum) for value in values)
    if operator == "sequence":
        return _contains_sequence(values, expected)
    return False


def _values_at_path(root: object, path: str) -> list[Any]:
    current: list[Any] = [root]
    for part in path.split("."):
        next_values: list[Any] = []
        for value in current:
            if isinstance(value, list):
                next_values.extend(_list_values(value, part))
                continue
            if isinstance(value, dict) and part in value:
                next_values.append(value[part])
                continue
            if hasattr(value, part):
                next_values.append(getattr(value, part))
        current = next_values
    return current


def _list_values(values: list[Any], part: str) -> list[Any]:
    result: list[Any] = []
    for item in values:
        if isinstance(item, dict) and part in item:
            result.append(item[part])
        elif hasattr(item, part):
            result.append(getattr(item, part))
    return result


def _present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Iterable):
        return bool(list(value))
    return True


def _in_range(value: object, minimum: object, maximum: object) -> bool:
    if not isinstance(value, int | float):
        return False
    if isinstance(minimum, int | float) and value < minimum:
        return False
    return not (isinstance(maximum, int | float) and value > maximum)


def _contains_sequence(values: list[Any], expected: object) -> bool:
    if not isinstance(expected, list):
        return False
    compact_values = [value for value in values if value is not None]
    if len(expected) > len(compact_values):
        return False
    return any(
        compact_values[start : start + len(expected)] == expected
        for start in range(len(compact_values) - len(expected) + 1)
    )


def _finding(
    rule: FormatRule,
    assertion: dict[str, Any],
    index: int,
    document: DocumentModel,
) -> CheckFinding:
    path = str(assertion.get("path", ""))
    return CheckFinding(
        id=f"property:{rule.id}:{index}",
        rule_id=rule.id,
        checker_id="property",
        category=rule.category,
        severity=rule.severity,
        location=FindingLocation(area="document_facts"),
        expected={"assertion": assertion},
        actual={"values": _values_at_path(document, path)[:10]},
        evidence=f"文档事实字段 {path} 未满足规则断言。",
        suggestion="请根据规则要求调整 Word 文档对应结构或格式。",
    )
