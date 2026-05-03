from dataclasses import dataclass
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired, run

from docchecker.services.docx_validator import (
    DocumentValidationError,
    validate_docx_package,
    validate_word_upload_path,
)


@dataclass(frozen=True)
class PreparedWordDocument:
    original_path: Path
    normalized_path: Path
    original_format: str
    normalized_format: str


def prepare_word_document(
    path: Path,
    *,
    max_size_bytes: int,
    libreoffice_command: str,
    conversion_timeout_seconds: int,
) -> PreparedWordDocument:
    validate_word_upload_path(path, max_size_bytes=max_size_bytes)
    suffix = path.suffix.lower()
    if suffix == ".docx":
        validate_docx_package(path)
        return PreparedWordDocument(
            original_path=path,
            normalized_path=path,
            original_format="docx",
            normalized_format="docx",
        )
    if suffix == ".doc":
        normalized_path = convert_doc_to_docx(
            path,
            libreoffice_command=libreoffice_command,
            conversion_timeout_seconds=conversion_timeout_seconds,
        )
        validate_docx_package(normalized_path)
        return PreparedWordDocument(
            original_path=path,
            normalized_path=normalized_path,
            original_format="doc",
            normalized_format="docx",
        )
    raise DocumentValidationError("仅支持 .doc 或 .docx 文件。")


def convert_doc_to_docx(
    path: Path,
    *,
    libreoffice_command: str,
    conversion_timeout_seconds: int,
) -> Path:
    output_path = path.with_suffix(".docx")
    output_path.unlink(missing_ok=True)
    command = [
        libreoffice_command,
        "--headless",
        "--convert-to",
        "docx",
        "--outdir",
        str(path.parent),
        str(path),
    ]
    timeout = None if conversion_timeout_seconds <= 0 else conversion_timeout_seconds
    try:
        result = run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError as exc:
        raise DocumentValidationError(
            f"LibreOffice 命令未找到：{libreoffice_command}。请安装 LibreOffice 或配置命令路径。"
        ) from exc
    except TimeoutExpired as exc:
        raise DocumentValidationError(
            f".doc 转换超时，超过 {conversion_timeout_seconds} 秒。"
        ) from exc
    _ensure_conversion_succeeded(result, output_path)
    return output_path


def _ensure_conversion_succeeded(result: CompletedProcess[str], output_path: Path) -> None:
    if result.returncode != 0:
        details = _conversion_output(result)
        raise DocumentValidationError(
            f".doc 转换失败，LibreOffice 返回码 {result.returncode}。{details}"
        )
    if not output_path.exists():
        details = _conversion_output(result)
        raise DocumentValidationError(f".doc 转换失败，未生成目标 .docx 文件。{details}")


def _conversion_output(result: CompletedProcess[str]) -> str:
    output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
    if not output:
        return "LibreOffice 未输出错误详情。"
    return f"LibreOffice 输出：{output}"
