from docchecker.checkers.base import relevant_rules
from docchecker.checkers.semantic_utils import (
    _abstract_count_finding,
    _abstract_word_count_rule_applies,
    _document_excerpt,
    _document_finding,
    _first_order_problem,
    _nonempty_paragraphs,
    _paragraph_finding,
    _section_index,
    _valid_caption_text,
)
from docchecker.domain.document import DocumentModel
from docchecker.domain.enums import RuleCategory
from docchecker.domain.findings import CheckFinding
from docchecker.domain.rules import FormatRule


class StructureChecker:
    checker_id = "structure_checker"
    supported_categories = {RuleCategory.structure}

    def check(self, document: DocumentModel, rules: list[FormatRule]) -> list[CheckFinding]:
        findings: list[CheckFinding] = []
        paragraphs = _nonempty_paragraphs(document)
        text = "\n".join(paragraph.text for paragraph in paragraphs)
        for rule in relevant_rules(rules, self.supported_categories):
            required = rule.expectation.get("requiredSections", [])
            if not isinstance(required, list):
                continue
            missing = [
                section
                for section in required
                if isinstance(section, str)
                and _section_index(section, document, text, paragraphs) is None
            ]
            if missing:
                findings.append(
                    _document_finding(
                        rule,
                        self.checker_id,
                        {"missingSections": []},
                        {"missingSections": missing},
                        f"论文缺少必要结构：{', '.join(missing)}。",
                        "请补齐缺失的论文结构，或在规则确认页关闭不适用的结构规则。",
                        excerpt=_document_excerpt(paragraphs),
                    )
                )
                continue
            order_problem = _first_order_problem(required, document, text, paragraphs)
            if order_problem:
                findings.append(
                    _document_finding(
                        rule,
                        self.checker_id,
                        {"sectionOrder": required},
                        {"outOfOrder": order_problem},
                        f"论文结构顺序不符合规则：{order_problem}。",
                        "请按规则要求调整论文组成部分的先后顺序。",
                        excerpt=_document_excerpt(paragraphs),
                    )
                )
        return findings


class TocChecker:
    checker_id = "toc_checker"
    supported_categories = {RuleCategory.toc}

    def check(self, document: DocumentModel, rules: list[FormatRule]) -> list[CheckFinding]:
        findings: list[CheckFinding] = []
        toc_fact = document.facts.toc
        for rule in relevant_rules(rules, self.supported_categories):
            if rule.expectation.get("requiresToc") and not toc_fact.has_title:
                findings.append(
                    _document_finding(
                        rule,
                        self.checker_id,
                        {"requiresToc": True},
                        {"requiresToc": False},
                        "论文未检测到目录标题。",
                        "请生成或补充目录，并确认目录标题为“目录”。",
                    )
                )
            if rule.expectation.get("requiresEntries") and toc_fact.entry_count == 0:
                findings.append(
                    _document_finding(
                        rule,
                        self.checker_id,
                        {"tocEntries": "编号 + 标题 + 页码"},
                        {"tocEntries": "未检测到目录项"},
                        "论文未检测到符合基本形态的目录项。",
                        "请检查目录是否自动生成，至少包含编号、标题和页码列。",
                    )
                )
            if rule.expectation.get("requiresTocField") and not toc_fact.has_field:
                findings.append(
                    _document_finding(
                        rule,
                        self.checker_id,
                        {"requiresTocField": True},
                        {"requiresTocField": False},
                        "论文未检测到 Word TOC 目录域。",
                        "请使用 Word 自动目录域生成目录，而不是手工录入目录文本。",
                    )
                )
            min_entry_count = rule.expectation.get("minEntryCount")
            if isinstance(min_entry_count, int | float) and toc_fact.entry_count < min_entry_count:
                findings.append(
                    _document_finding(
                        rule,
                        self.checker_id,
                        {"minEntryCount": min_entry_count},
                        {"entryCount": toc_fact.entry_count},
                        "目录条目数量少于规则要求。",
                        "请确认目录已覆盖规定层级的标题。",
                    )
                )
        return findings


class CaptionChecker:
    checker_id = "caption_checker"
    supported_categories = {RuleCategory.caption}

    def check(self, document: DocumentModel, rules: list[FormatRule]) -> list[CheckFinding]:
        findings: list[CheckFinding] = []
        paragraph_by_index = {paragraph.index: paragraph for paragraph in document.paragraphs}
        for rule in relevant_rules(rules, self.supported_categories):
            if rule.expectation.get("requiresTableCaption") is True:
                missing = [
                    table.index
                    for table in document.facts.tables
                    if not table.caption_text
                ]
                if missing:
                    findings.append(
                        _document_finding(
                            rule,
                            self.checker_id,
                            {"requiresTableCaption": True},
                            {"missingTableCaptionIndexes": missing},
                            "存在未检测到表题的表格。",
                            "请为每个表格补充表题，并放在规范要求的位置。",
                        )
                    )
            expected_position = rule.expectation.get("tableCaptionPosition")
            if expected_position in {"before", "after"}:
                misplaced = [
                    table.index
                    for table in document.facts.tables
                    if table.caption_text and table.caption_position != expected_position
                ]
                if misplaced:
                    findings.append(
                        _document_finding(
                            rule,
                            self.checker_id,
                            {"tableCaptionPosition": expected_position},
                            {"misplacedTableCaptionIndexes": misplaced},
                            "表题位置不符合规则要求。",
                            "请按规则要求把表题放在表格上方或下方。",
                        )
                    )
            invalid = [
                caption
                for caption in document.facts.captions
                if not _valid_caption_text(caption.text)
            ]
            for caption in invalid:
                paragraph = paragraph_by_index.get(caption.paragraph_index)
                if paragraph is None:
                    continue
                findings.append(
                    _paragraph_finding(
                        rule,
                        self.checker_id,
                        paragraph,
                        {"captionPattern": "图1.1 题名 / 表1.1 题名"},
                        {"caption": caption.text},
                        f"题注编号或空格格式不符合规则：{caption.text}",
                        "请按“图1.1 题名”或“表1.1 题名”的格式调整题注。",
                    )
                )
            for field, attr in [
                ("fontFamilyEastAsia", "font_family_east_asia"),
                ("fontSizePt", "font_size_pt"),
                ("alignment", "alignment"),
            ]:
                expected = rule.expectation.get(field)
                if expected is None:
                    continue
                for caption in document.facts.captions:
                    paragraph = paragraph_by_index.get(caption.paragraph_index)
                    if paragraph is None or getattr(paragraph, attr) == expected:
                        continue
                    findings.append(
                        _paragraph_finding(
                            rule,
                            self.checker_id,
                            paragraph,
                            {field: expected},
                            {field: getattr(paragraph, attr)},
                            "题注段落格式不符合规则要求。",
                            "请调整图题、表题的字体、字号或对齐方式。",
                        )
                    )
        return findings


class ReferenceChecker:
    checker_id = "reference_checker"
    supported_categories = {RuleCategory.reference}

    def check(self, document: DocumentModel, rules: list[FormatRule]) -> list[CheckFinding]:
        findings: list[CheckFinding] = []
        paragraphs = _nonempty_paragraphs(document)
        references = [
            paragraph
            for paragraph in paragraphs
            if any(
                entry.paragraph_index == paragraph.index
                for entry in document.facts.references.entries
            )
        ]
        for rule in relevant_rules(rules, self.supported_categories):
            if (
                rule.expectation.get("requiresSection")
                and not document.facts.references.has_section
            ):
                findings.append(
                    _document_finding(
                        rule,
                        self.checker_id,
                        {"requiresSection": True},
                        {"requiresSection": False},
                        "论文未检测到参考文献章节标题。",
                        "请补充参考文献章节，并将参考文献条目放在该章节下。",
                    )
                )
            if rule.expectation.get("requiresReferences") and not references:
                findings.append(
                    _document_finding(
                        rule,
                        self.checker_id,
                        {"references": "至少 1 条编号参考文献"},
                        {"references": "未检测到编号参考文献"},
                        "论文未检测到形如 [1] 的参考文献条目。",
                        "请检查参考文献部分是否存在，并按编号顺序列出。",
                    )
                )
                continue
            actual = [entry.number for entry in document.facts.references.entries]
            expected = list(range(1, len(actual) + 1))
            if rule.expectation.get("numberingContinuous", True) and actual != expected:
                findings.append(
                    _document_finding(
                        rule,
                        self.checker_id,
                        {"referenceOrder": expected},
                        {"referenceOrder": actual},
                        "参考文献编号不连续或顺序异常。",
                        "请按正文引用出现顺序或规范要求重新编号参考文献。",
                    )
                )
            for paragraph in references:
                if len(paragraph.text.split(".", maxsplit=1)) < 2 and "，" not in paragraph.text:
                    findings.append(
                        _paragraph_finding(
                            rule,
                            self.checker_id,
                            paragraph,
                            {"referenceEntry": "编号 + 作者/题名/来源信息"},
                            {"referenceEntry": paragraph.text},
                            f"参考文献条目信息可能不完整：{paragraph.text}",
                            "请补充作者、题名、来源、年份等基本著录信息。",
                        )
                    )
        return findings


class AbstractChecker:
    checker_id = "abstract_checker"
    supported_categories = {RuleCategory.abstract}

    def check(self, document: DocumentModel, rules: list[FormatRule]) -> list[CheckFinding]:
        findings: list[CheckFinding] = []
        zh_abstract = next(
            (fact for fact in document.facts.abstracts if fact.language == "zh"),
            None,
        )
        en_abstract = next(
            (fact for fact in document.facts.abstracts if fact.language == "en"),
            None,
        )
        for rule in relevant_rules(rules, self.supported_categories):
            if rule.expectation.get("requiresChineseAbstract") and zh_abstract is None:
                findings.append(
                    _document_finding(
                        rule,
                        self.checker_id,
                        {"requiresChineseAbstract": True},
                        {"requiresChineseAbstract": False},
                        "论文未检测到中文摘要。",
                        "请补充中文摘要章节。",
                    )
                )
            if rule.expectation.get("requiresEnglishAbstract") and en_abstract is None:
                findings.append(
                    _document_finding(
                        rule,
                        self.checker_id,
                        {"requiresEnglishAbstract": True},
                        {"requiresEnglishAbstract": False},
                        "论文未检测到英文摘要。",
                        "请补充英文摘要或 Abstract 章节。",
                    )
                )
            if rule.expectation.get("requiresKeywords"):
                missing_keywords = [
                    fact.language for fact in document.facts.abstracts if not fact.has_keywords
                ]
                if missing_keywords:
                    findings.append(
                        _document_finding(
                            rule,
                            self.checker_id,
                            {"requiresKeywords": True},
                            {"abstractsMissingKeywords": missing_keywords},
                            "摘要章节未检测到关键词段落。",
                            "请在摘要后补充关键词或 Keywords 段落。",
                        )
                    )
            for fact in document.facts.abstracts:
                min_count = rule.expectation.get("minWordCount")
                max_count = rule.expectation.get("maxWordCount")
                if (
                    isinstance(min_count, int | float)
                    and _abstract_word_count_rule_applies(rule, fact.language)
                    and fact.word_count < min_count
                ):
                    findings.append(
                        _abstract_count_finding(rule, fact, {"minWordCount": min_count})
                    )
                if (
                    isinstance(max_count, int | float)
                    and _abstract_word_count_rule_applies(rule, fact.language)
                    and fact.word_count > max_count
                ):
                    findings.append(
                        _abstract_count_finding(rule, fact, {"maxWordCount": max_count})
                    )
        return findings


