from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from docchecker.services.docx_validator import DocumentValidationError

UPLOAD_CHUNK_SIZE = 1024 * 1024


class StoredFile:
    def __init__(self, document_id: str, original_filename: str, path: Path) -> None:
        self.document_id = document_id
        self.original_filename = original_filename
        self.path = path


class LocalFileStorage:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.documents_dir = root / "documents"
        self.reports_dir = root / "reports"
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    async def save_upload(self, upload: UploadFile, *, max_size_bytes: int) -> StoredFile:
        document_id = f"doc_{uuid4().hex}"
        extension = Path(upload.filename or "").suffix.lower()
        path = self.documents_dir / f"{document_id}{extension}"
        bytes_written = 0
        try:
            with path.open("wb") as target:
                while chunk := await upload.read(UPLOAD_CHUNK_SIZE):
                    next_size = bytes_written + len(chunk)
                    if next_size > max_size_bytes:
                        raise DocumentValidationError(
                            f"文件大小 {next_size} bytes 超过限制 {max_size_bytes} bytes。"
                        )
                    bytes_written = next_size
                    target.write(chunk)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return StoredFile(document_id, upload.filename or "unknown.docx", path)

    def report_path(self, report_id: str) -> Path:
        return self.reports_dir / f"{report_id}.md"
