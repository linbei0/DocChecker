from pathlib import Path
from zipfile import BadZipFile, ZipFile

REQUIRED_DOCX_PARTS = {"[Content_Types].xml", "word/document.xml"}
SUPPORTED_WORD_EXTENSIONS = {".doc", ".docx"}


class DocumentValidationError(ValueError):
    """文档校验失败。"""


def validate_word_upload_path(path: Path, *, max_size_bytes: int) -> None:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_WORD_EXTENSIONS:
        raise DocumentValidationError("仅支持 .doc 或 .docx 文件。")
    size = path.stat().st_size
    if size > max_size_bytes:
        raise DocumentValidationError(f"文件大小 {size} bytes 超过限制 {max_size_bytes} bytes。")


def validate_docx_path(path: Path, *, max_size_bytes: int) -> None:
    if path.suffix.lower() != ".docx":
        raise DocumentValidationError("仅支持 .docx 文件；.doc 需要用户先显式转换。")
    validate_word_upload_path(path, max_size_bytes=max_size_bytes)
    validate_docx_package(path)


def validate_docx_package(path: Path) -> None:
    if path.suffix.lower() != ".docx":
        raise DocumentValidationError("内部解析文件必须是 .docx。")
    try:
        with ZipFile(path) as package:
            names = set(package.namelist())
    except BadZipFile as exc:
        raise DocumentValidationError("文件不是有效的 .docx ZIP 包。") from exc
    missing = REQUIRED_DOCX_PARTS - names
    if missing:
        raise DocumentValidationError(f"缺少必要 OOXML 部件：{', '.join(sorted(missing))}。")
