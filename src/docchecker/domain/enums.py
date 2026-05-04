from enum import StrEnum


class Severity(StrEnum):
    blocker = "blocker"
    major = "major"
    minor = "minor"
    info = "info"


class RuleCategory(StrEnum):
    page = "page"
    font = "font"
    paragraph = "paragraph"
    heading = "heading"
    header_footer = "header_footer"
    caption = "caption"
    reference = "reference"
    structure = "structure"
    toc = "toc"
    abstract = "abstract"


class SourceType(StrEnum):
    manual = "manual"
    requirement_doc = "requirement_doc"
    template = "template"


class Certainty(StrEnum):
    certain = "certain"
    probable = "probable"
    unknown = "unknown"


class TaskStatus(StrEnum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class DraftRuleSetStatus(StrEnum):
    draft = "draft"
    published = "published"
