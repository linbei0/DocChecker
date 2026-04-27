from pathlib import Path
from zipfile import ZipFile

from docx import Document
from lxml import etree

WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def extract_requirement_text(path: Path) -> str:
    document = Document(path)
    chunks: list[str] = []
    chunks.extend(
        paragraph.text.strip()
        for paragraph in document.paragraphs
        if paragraph.text.strip()
    )
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                chunks.append(" | ".join(cells))
    chunks.extend(_extract_comment_text(path))
    return "\n".join(chunks)


def _extract_comment_text(path: Path) -> list[str]:
    with ZipFile(path) as package:
        if "word/comments.xml" not in package.namelist():
            return []
        comments_xml = package.read("word/comments.xml")

    root = etree.fromstring(comments_xml)
    comments: list[str] = []
    for comment in root.xpath("//w:comment", namespaces=WORD_NS):
        text = "".join(comment.xpath(".//w:t/text()", namespaces=WORD_NS)).strip()
        if text:
            comments.append(text)
    return comments
