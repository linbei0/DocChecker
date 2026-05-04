from dataclasses import dataclass
from typing import Any

from docchecker.domain.enums import RuleCategory


@dataclass(frozen=True)
class CheckerCapability:
    category: RuleCategory
    fields: frozenset[str]
    scope_prefixes: tuple[str, ...] = ()
    field_descriptions: dict[str, str] | None = None
    example_expectation: dict[str, object] | None = None

    def supports(self, *, scope: str, field: str) -> bool:
        if field not in self.fields:
            return False
        return self.supports_scope(scope)

    def supports_scope(self, scope: str) -> bool:
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
        field_descriptions={
            "page_width_cm": "页面宽度，单位厘米。",
            "page_height_cm": "页面高度，单位厘米。",
            "margin_top_cm": "上页边距，单位厘米。",
            "margin_bottom_cm": "下页边距，单位厘米。",
            "margin_left_cm": "左页边距，单位厘米。",
            "margin_right_cm": "右页边距，单位厘米。",
        },
        example_expectation={"margin_top_cm": 2.5, "margin_bottom_cm": 2.5},
    ),
    CheckerCapability(
        category=RuleCategory.font,
        fields=frozenset({"fontFamilyEastAsia", "fontSizePt", "bold"}),
        field_descriptions={
            "fontFamilyEastAsia": "中文字体名称，例如宋体、黑体。",
            "fontSizePt": "字号，单位磅；小四应转换为 12。",
            "bold": "是否加粗。",
        },
        example_expectation={"fontFamilyEastAsia": "宋体", "fontSizePt": 12},
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
        field_descriptions={
            "alignment": "段落对齐方式：left、center、right、justify。",
            "firstLineIndentCm": "首行缩进，单位厘米。",
            "lineSpacing": "行距倍数。",
            "spaceBeforePt": "段前间距，单位磅。",
            "spaceAfterPt": "段后间距，单位磅。",
            "fontFamilyEastAsia": "段落中文字体名称。",
            "fontSizePt": "段落字号，单位磅。",
        },
        example_expectation={"lineSpacing": 1.5, "firstLineIndentCm": 0.74},
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
        field_descriptions={
            "fontFamilyEastAsia": "标题中文字体名称。",
            "fontSizePt": "标题字号，单位磅。",
            "bold": "标题是否加粗。",
            "alignment": "标题对齐方式。",
            "spaceBeforePt": "标题段前间距，单位磅。",
            "spaceAfterPt": "标题段后间距，单位磅。",
        },
        example_expectation={"fontFamilyEastAsia": "黑体", "fontSizePt": 16, "bold": True},
    ),
    CheckerCapability(
        category=RuleCategory.header_footer,
        fields=frozenset({"textContains", "requiresPageNumber"}),
        scope_prefixes=("document.header_footer", "header_footer", "header", "footer"),
        field_descriptions={
            "textContains": "页眉或页脚必须包含的文本片段。",
            "requiresPageNumber": "页眉或页脚是否必须包含页码域或页码文本。",
        },
        example_expectation={"requiresPageNumber": True},
    ),
    CheckerCapability(
        category=RuleCategory.caption,
        fields=frozenset({"captionPattern"}),
        scope_prefixes=("document.caption", "caption"),
        field_descriptions={"captionPattern": "图题、表题编号和题名模式。"},
        example_expectation={"captionPattern": "图1.1 题名 / 表1.1 题名"},
    ),
    CheckerCapability(
        category=RuleCategory.reference,
        fields=frozenset({"requiresReferences", "numbering"}),
        scope_prefixes=("document.references", "reference"),
        field_descriptions={
            "requiresReferences": "是否必须包含参考文献章节。",
            "numbering": "参考文献编号模式，例如 bracketed。",
        },
        example_expectation={"requiresReferences": True, "numbering": "bracketed"},
    ),
    CheckerCapability(
        category=RuleCategory.structure,
        fields=frozenset({"requiredSections"}),
        scope_prefixes=("document.structure", "structure"),
        field_descriptions={"requiredSections": "文档必须包含的章节名称列表。"},
        example_expectation={"requiredSections": ["中文摘要", "正文", "参考文献"]},
    ),
    CheckerCapability(
        category=RuleCategory.toc,
        fields=frozenset({"requiresToc", "requiresEntries"}),
        scope_prefixes=("document.toc", "toc"),
        field_descriptions={
            "requiresToc": "是否必须包含目录。",
            "requiresEntries": "目录是否必须包含条目。",
        },
        example_expectation={"requiresToc": True, "requiresEntries": True},
    ),
)


def capability_manifest() -> dict[str, Any]:
    """生成给 LLM 和诊断面板复用的能力清单，禁止候选规则越权造字段。"""

    return {
        "categories": [
            {
                "category": capability.category.value,
                "scope_prefixes": list(capability.scope_prefixes),
                "fields": sorted(capability.fields),
                "field_descriptions": capability.field_descriptions or {},
                "example_expectation": capability.example_expectation or {},
            }
            for capability in CHECKER_CAPABILITIES
        ],
        "unsupported_policy": (
            "无法完全映射到 category、scope_prefixes、fields 的要求必须返回 "
            "checkability=unsupported，expectation 使用空对象，不允许自造字段。"
        ),
        "rule_dsl": {
            "key": "$dsl",
            "facts_backend": {
                "backend": "facts",
                "operators": ["equals", "matches", "contains", "exists", "range", "sequence"],
                "required": ["backend", "path", "operator"],
                "example": {
                    "backend": "facts",
                    "path": "facts.headers_footers.text",
                    "operator": "contains",
                    "value": "学校",
                },
            },
            "ooxml_backend": {
                "backend": "ooxml",
                "operators": ["xpath", "schematron"],
                "xpath_required": ["backend", "operator", "part", "expression"],
                "schematron_required": ["backend", "operator", "part", "schema"],
            },
        },
    }


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


def supports_scope(category: RuleCategory, *, scope: str) -> bool:
    return any(
        capability.category == category and capability.supports_scope(scope)
        for capability in CHECKER_CAPABILITIES
    )
