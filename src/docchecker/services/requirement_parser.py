from pathlib import Path
from zipfile import ZipFile

from docx import Document
from lxml import etree

WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def extract_requirement_text(path: Path) -> str:
    document = Document(path)
    chunks: list[str] = []
    for index, paragraph in enumerate(document.paragraphs, start=1):
        text = paragraph.text.strip()
        if text:
            chunks.append(f"paragraph:{index}\t{text}")
    for table_index, table in enumerate(document.tables, start=1):
        for row_index, row in enumerate(table.rows, start=1):
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                chunks.append(f"table:{table_index},row:{row_index}\t{' | '.join(cells)}")
    chunks.extend(_extract_comment_text(path))
    return "\n".join(chunks)


def _extract_comment_text(path: Path) -> list[str]:
    with ZipFile(path) as package:
        if "word/comments.xml" not in package.namelist():
            return []
        comments_xml = package.read("word/comments.xml")

    root = etree.fromstring(comments_xml)
    comments: list[str] = []
    for comment_index, comment in enumerate(
        root.xpath("//w:comment", namespaces=WORD_NS),
        start=1,
    ):
        text = "".join(comment.xpath(".//w:t/text()", namespaces=WORD_NS)).strip()
        if text:
            comment_id = comment.get(f"{{{WORD_NS['w']}}}id")
            location = f"comment:{comment_id or comment_index}"
            comments.append(f"{location}\t{text}")
    return comments
