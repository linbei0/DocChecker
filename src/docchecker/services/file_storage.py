from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile


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

    async def save_upload(self, upload: UploadFile) -> StoredFile:
        document_id = f"doc_{uuid4().hex}"
        extension = Path(upload.filename or "").suffix.lower()
        path = self.documents_dir / f"{document_id}{extension}"
        with path.open("wb") as target:
            while chunk := await upload.read(1024 * 1024):
                target.write(chunk)
        return StoredFile(document_id, upload.filename or "unknown.docx", path)

    def report_path(self, report_id: str) -> Path:
        return self.reports_dir / f"{report_id}.md"
