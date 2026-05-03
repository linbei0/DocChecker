from pathlib import Path
from shutil import copyfile
from subprocess import CompletedProcess, TimeoutExpired

import pytest
from docx import Document

from docchecker.services.docx_validator import DocumentValidationError
from docchecker.services.word_document_preparer import prepare_word_document


def _create_docx(path: Path, text: str = "正文内容") -> None:
    document = Document()
    document.add_paragraph(text)
    document.save(path)


def test_prepare_docx_validates_package(tmp_path: Path) -> None:
    path = tmp_path / "paper.docx"
    _create_docx(path)

    prepared = prepare_word_document(
        path,
        max_size_bytes=1024 * 1024,
        libreoffice_command="soffice",
        conversion_timeout_seconds=60,
    )

    assert prepared.original_path == path
    assert prepared.normalized_path == path
    assert prepared.original_format == "docx"
    assert prepared.normalized_format == "docx"


def test_prepare_doc_converts_to_docx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    doc_path = tmp_path / "paper.doc"
    doc_path.write_bytes(b"legacy word content")
    converted_template = tmp_path / "converted-template.docx"
    _create_docx(converted_template)

    def fake_run(command, **kwargs):
        assert command[:4] == ["soffice", "--headless", "--convert-to", "docx"]
        assert kwargs["timeout"] == 60
        copyfile(converted_template, doc_path.with_suffix(".docx"))
        return CompletedProcess(command, 0, stdout="convert ok", stderr="")

    monkeypatch.setattr("docchecker.services.word_document_preparer.run", fake_run)

    prepared = prepare_word_document(
        doc_path,
        max_size_bytes=1024 * 1024,
        libreoffice_command="soffice",
        conversion_timeout_seconds=60,
    )

    assert prepared.original_path == doc_path
    assert prepared.normalized_path == doc_path.with_suffix(".docx")
    assert prepared.original_format == "doc"
    assert prepared.normalized_format == "docx"


def test_prepare_doc_reports_missing_libreoffice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc_path = tmp_path / "paper.doc"
    doc_path.write_bytes(b"legacy word content")

    def fake_run(command, **kwargs):
        raise FileNotFoundError(command[0])

    monkeypatch.setattr("docchecker.services.word_document_preparer.run", fake_run)

    with pytest.raises(DocumentValidationError, match="LibreOffice 命令未找到"):
        prepare_word_document(
            doc_path,
            max_size_bytes=1024 * 1024,
            libreoffice_command="missing-soffice",
            conversion_timeout_seconds=60,
        )


def test_prepare_doc_reports_conversion_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc_path = tmp_path / "paper.doc"
    doc_path.write_bytes(b"legacy word content")

    def fake_run(command, **kwargs):
        raise TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr("docchecker.services.word_document_preparer.run", fake_run)

    with pytest.raises(DocumentValidationError, match="转换超时"):
        prepare_word_document(
            doc_path,
            max_size_bytes=1024 * 1024,
            libreoffice_command="soffice",
            conversion_timeout_seconds=60,
        )


def test_prepare_doc_reports_nonzero_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc_path = tmp_path / "paper.doc"
    doc_path.write_bytes(b"legacy word content")

    def fake_run(command, **kwargs):
        return CompletedProcess(command, 1, stdout="", stderr="failed")

    monkeypatch.setattr("docchecker.services.word_document_preparer.run", fake_run)

    with pytest.raises(DocumentValidationError, match="返回码 1"):
        prepare_word_document(
            doc_path,
            max_size_bytes=1024 * 1024,
            libreoffice_command="soffice",
            conversion_timeout_seconds=60,
        )


def test_prepare_doc_reports_missing_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc_path = tmp_path / "paper.doc"
    doc_path.write_bytes(b"legacy word content")

    def fake_run(command, **kwargs):
        return CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr("docchecker.services.word_document_preparer.run", fake_run)

    with pytest.raises(DocumentValidationError, match="未生成目标 .docx 文件"):
        prepare_word_document(
            doc_path,
            max_size_bytes=1024 * 1024,
            libreoffice_command="soffice",
            conversion_timeout_seconds=60,
        )
