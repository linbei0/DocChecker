from pathlib import Path
from zipfile import BadZipFile, ZipFile

REQUIRED_DOCX_PARTS = {"[Content_Types].xml", "word/document.xml"}


class DocumentValidationError(ValueError):
    """文档校验失败。"""


def validate_docx_path(path: Path, *, max_size_bytes: int) -> None:
    if path.suffix.lower() != ".docx":
        raise DocumentValidationError("仅支持 .docx 文件；.doc 需要用户先显式转换。")
    size = path.stat().st_size
    if size > max_size_bytes:
        raise DocumentValidationError(f"文件大小 {size} bytes 超过限制 {max_size_bytes} bytes。")
    try:
        with ZipFile(path) as package:
            names = set(package.namelist())
    except BadZipFile as exc:
        raise DocumentValidationError("文件不是有效的 .docx ZIP 包。") from exc
    missing = REQUIRED_DOCX_PARTS - names
    if missing:
        raise DocumentValidationError(f"缺少必要 OOXML 部件：{', '.join(sorted(missing))}。")
