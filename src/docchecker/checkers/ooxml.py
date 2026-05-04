from typing import Any

from lxml import etree
from lxml.isoschematron import Schematron

from docchecker.checkers.rule_dsl import schematron_assertions, xpath_assertions
from docchecker.domain.document import DocumentModel
from docchecker.domain.enums import RuleCategory, Severity
from docchecker.domain.findings import CheckFinding, FindingLocation
from docchecker.domain.rules import FormatRule

OOXML_NAMESPACES = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


class OoxmlRuleChecker:
    checker_id = "ooxml"
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
            findings.extend(_xpath_findings(document, rule))
            findings.extend(_schematron_findings(document, rule))
        return findings


def _xpath_findings(document: DocumentModel, rule: FormatRule) -> list[CheckFinding]:
    findings: list[CheckFinding] = []
    for index, assertion in enumerate(xpath_assertions(rule.expectation)):
        part_name = assertion.get("part")
        expression = assertion.get("expression")
        if not isinstance(part_name, str) or not isinstance(expression, str):
            continue
        xml = document.facts.xml_parts.get(part_name)
        if xml is None:
            findings.append(
                _finding(rule, part_name, expression, index, {"missing_part": part_name})
            )
            continue
        root = etree.fromstring(xml.encode("utf-8"))
        result = root.xpath(expression, namespaces=OOXML_NAMESPACES)
        if not _truthy_xpath_result(result):
            findings.append(_finding(rule, part_name, expression, index, {"result": result}))
    return findings


def _schematron_findings(document: DocumentModel, rule: FormatRule) -> list[CheckFinding]:
    findings: list[CheckFinding] = []
    for index, assertion in enumerate(schematron_assertions(rule.expectation)):
        part_name = assertion.get("part")
        schema_text = assertion.get("schema")
        if not isinstance(part_name, str) or not isinstance(schema_text, str):
            continue
        xml = document.facts.xml_parts.get(part_name)
        if xml is None:
            findings.append(
                _finding(rule, part_name, "schematron", index, {"missing_part": part_name})
            )
            continue
        schema_root = etree.fromstring(schema_text.encode("utf-8"))
        document_root = etree.fromstring(xml.encode("utf-8"))
        schematron = Schematron(schema_root)
        if not schematron.validate(document_root):
            findings.append(
                _finding(
                    rule,
                    part_name,
                    "schematron",
                    index,
                    {"validation_report": str(schematron.error_log)},
                )
            )
    return findings


def _truthy_xpath_result(result: Any) -> bool:
    if isinstance(result, bool):
        return result
    if isinstance(result, int | float):
        return result != 0
    if isinstance(result, str):
        return bool(result.strip())
    if isinstance(result, list):
        return bool(result)
    return result is not None


def _finding(
    rule: FormatRule,
    part_name: str,
    expression: str,
    index: int,
    actual: dict[str, Any],
) -> CheckFinding:
    return CheckFinding(
        id=f"ooxml:{rule.id}:{index}",
        rule_id=rule.id,
        checker_id="ooxml",
        category=rule.category,
        severity=rule.severity if rule.severity else Severity.major,
        location=FindingLocation(area="ooxml", xml_path=part_name),
        expected={"expression": expression, "part": part_name},
        actual=actual,
        evidence=f"OOXML 结构断言未通过：{part_name} / {expression}",
        suggestion="请检查 Word 文档底层结构或调整对应格式规则。",
    )
