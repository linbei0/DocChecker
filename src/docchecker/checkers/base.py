from typing import Protocol

from docchecker.domain.document import DocumentModel
from docchecker.domain.enums import RuleCategory
from docchecker.domain.findings import CheckFinding
from docchecker.domain.rules import FormatRule


class Checker(Protocol):
    checker_id: str
    supported_categories: set[RuleCategory]

    def check(self, document: DocumentModel, rules: list[FormatRule]) -> list[CheckFinding]:
        ...


def relevant_rules(rules: list[FormatRule], categories: set[RuleCategory]) -> list[FormatRule]:
    return [rule for rule in rules if rule.enabled and rule.category in categories]
