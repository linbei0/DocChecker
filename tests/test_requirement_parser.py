from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from docx import Document

from docchecker.services.requirement_parser import extract_requirement_text


def test_extract_requirement_text_includes_word_comments(tmp_path: Path) -> None:
    path = tmp_path / "requirement.docx"
    document = Document()
    document.add_paragraph("中文论文题目")
    document.save(path)

    with ZipFile(path, "a", ZIP_DEFLATED) as package:
        package.writestr(
            "word/comments.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:comment w:id="0" w:author="user">
    <w:p><w:r><w:t>三号宋体加粗居中，一般不多于30个字。</w:t></w:r></w:p>
  </w:comment>
</w:comments>
""",
        )

    text = extract_requirement_text(path)

    assert "中文论文题目" in text
    assert "三号宋体加粗居中" in text
