from dataclasses import dataclass

from docchecker.domain.enums import RuleCategory


@dataclass(frozen=True)
class CheckerCapability:
    category: RuleCategory
    fields: frozenset[str]
    scope_prefixes: tuple[str, ...] = ()

    def supports(self, *, scope: str, field: str) -> bool:
        if field not in self.fields:
            return False
        if not self.scope_prefixes:
            return True
        return any(scope.startswith(prefix) for prefix in self.scope_prefixes)


CHECKER_CAPABILITIES: tuple[CheckerCapability, ...] = (
    CheckerCapability(
        category=RuleCategory.page,
        fields=frozenset(
            {
                "page_width_cm",
                "page_height_cm",
                "margin_top_cm",
                "margin_bottom_cm",
                "margin_left_cm",
                "margin_right_cm",
            }
        ),
        scope_prefixes=("document.page", "page", "whole_document"),
    ),
    CheckerCapability(
        category=RuleCategory.font,
        fields=frozenset({"fontFamilyEastAsia", "fontSizePt", "bold"}),
    ),
    CheckerCapability(
        category=RuleCategory.paragraph,
        fields=frozenset(
            {
                "alignment",
                "firstLineIndentCm",
                "lineSpacing",
                "spaceBeforePt",
                "spaceAfterPt",
                "fontFamilyEastAsia",
                "fontSizePt",
            }
        ),
    ),
    CheckerCapability(
        category=RuleCategory.heading,
        fields=frozenset(
            {
                "fontFamilyEastAsia",
                "fontSizePt",
                "bold",
                "alignment",
                "spaceBeforePt",
                "spaceAfterPt",
            }
        ),
        scope_prefixes=("heading", "title", "cover.title"),
    ),
    CheckerCapability(
        category=RuleCategory.caption,
        fields=frozenset({"captionPattern"}),
        scope_prefixes=("document.caption", "caption"),
    ),
    CheckerCapability(
        category=RuleCategory.reference,
        fields=frozenset({"requiresReferences", "numbering"}),
        scope_prefixes=("document.references", "reference"),
    ),
    CheckerCapability(
        category=RuleCategory.structure,
        fields=frozenset({"requiredSections"}),
        scope_prefixes=("document.structure", "structure"),
    ),
    CheckerCapability(
        category=RuleCategory.toc,
        fields=frozenset({"requiresToc", "requiresEntries"}),
        scope_prefixes=("document.toc", "toc"),
    ),
)


def supported_expectation(
    category: RuleCategory,
    scope: str,
    expectation: dict[str, object],
) -> dict[str, object]:
    return {
        field: value
        for field, value in expectation.items()
        if supports_field(category, scope=scope, field=field)
    }


def unsupported_expectation_fields(
    category: RuleCategory,
    scope: str,
    expectation: dict[str, object],
) -> list[str]:
    return [
        field
        for field in expectation
        if not supports_field(category, scope=scope, field=field)
    ]


def supports_field(category: RuleCategory, *, scope: str, field: str) -> bool:
    return any(
        capability.category == category and capability.supports(scope=scope, field=field)
        for capability in CHECKER_CAPABILITIES
    )
