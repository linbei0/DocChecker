from typing import Any, Literal

RuleDslBackend = Literal["facts", "ooxml"]
RuleDslOperator = Literal[
    "equals",
    "matches",
    "contains",
    "exists",
    "range",
    "sequence",
    "xpath",
    "schematron",
]

FACT_OPERATORS = {"equals", "matches", "contains", "exists", "range", "sequence"}
OOXML_OPERATORS = {"xpath", "schematron"}
EXECUTION_KEYS = {"$dsl", "$facts", "$xpath", "$schematron"}


def has_execution_assertions(expectation: dict[str, object]) -> bool:
    return any(key in expectation for key in EXECUTION_KEYS)


def fact_assertions(expectation: dict[str, object]) -> list[dict[str, Any]]:
    assertions: list[dict[str, Any]] = []
    legacy = expectation.get("$facts")
    if isinstance(legacy, list):
        assertions.extend(item for item in legacy if isinstance(item, dict))
    assertions.extend(
        item
        for item in _dsl_items(expectation)
        if item.get("backend") == "facts" and item.get("operator") in FACT_OPERATORS
    )
    return assertions


def xpath_assertions(expectation: dict[str, object]) -> list[dict[str, Any]]:
    assertions: list[dict[str, Any]] = []
    legacy = expectation.get("$xpath")
    if isinstance(legacy, list):
        assertions.extend(item for item in legacy if isinstance(item, dict))
    assertions.extend(
        item
        for item in _dsl_items(expectation)
        if item.get("backend") == "ooxml" and item.get("operator") == "xpath"
    )
    return assertions


def schematron_assertions(expectation: dict[str, object]) -> list[dict[str, Any]]:
    assertions: list[dict[str, Any]] = []
    legacy = expectation.get("$schematron")
    if isinstance(legacy, list):
        assertions.extend(item for item in legacy if isinstance(item, dict))
    assertions.extend(
        item
        for item in _dsl_items(expectation)
        if item.get("backend") == "ooxml" and item.get("operator") == "schematron"
    )
    return assertions


def execution_expectation(expectation: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in expectation.items() if key in EXECUTION_KEYS}


def non_execution_expectation(expectation: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in expectation.items() if key not in EXECUTION_KEYS}


def _dsl_items(expectation: dict[str, object]) -> list[dict[str, Any]]:
    items = expectation.get("$dsl")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]
