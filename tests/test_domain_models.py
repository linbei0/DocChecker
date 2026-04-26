from pydantic import ValidationError

from docchecker.domain.enums import RuleCategory, Severity, SourceType
from docchecker.domain.rules import FormatRule, RuleSource, RuleTarget


def test_format_rule_rejects_unknown_fields() -> None:
    try:
        FormatRule(
            id="body_font",
            category=RuleCategory.font,
            target=RuleTarget(scope="body.paragraph"),
            expectation={"fontSizePt": 12},
            severity=Severity.major,
            source=RuleSource(type=SourceType.manual, excerpt="正文小四"),
            confidence=1,
            unexpected=True,
        )
    except ValidationError as exc:
        assert "unexpected" in str(exc)
    else:
        raise AssertionError("FormatRule 应拒绝未知字段")
