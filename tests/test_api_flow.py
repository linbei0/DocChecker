from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient

from docchecker.api import main
from docchecker.api.main import app
from docchecker.services.word_document_preparer import PreparedWordDocument


def _create_docx(path: Path, text: str) -> None:
    document = Document()
    document.add_paragraph(text)
    document.save(path)


def _fake_prepare_doc_upload(path: Path, **kwargs) -> PreparedWordDocument:
    normalized_path = path.with_suffix(".docx")
    _create_docx(normalized_path, "正文内容")
    return PreparedWordDocument(
        original_path=path,
        normalized_path=normalized_path,
        original_format=path.suffix.lower().lstrip("."),
        normalized_format="docx",
    )


def test_manual_ruleset_check_flow(tmp_path: Path) -> None:
    docx_path = tmp_path / "paper.docx"
    _create_docx(docx_path, "正文内容")
    client = TestClient(app)

    with docx_path.open("rb") as file:
        document_response = client.post(
            "/api/documents",
            files={
                "file": (
                    "paper.docx",
                    file,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
    assert document_response.status_code == 200
    document_id = document_response.json()["document_id"]

    draft_response = client.post(
        "/api/draft-rulesets",
        json={
            "document_id": document_id,
            "source_type": "manual",
            "manual_text": "正文宋体小四，1.5倍行距，页边距上下2.5cm。",
        },
    )
    assert draft_response.status_code == 200
    draft = draft_response.json()
    assert draft["rules"]
    assert draft["extraction_summary"]["structured_rules"] == len(draft["rules"])
    assert "unsupported_requirements" in draft

    publish_response = client.post(f"/api/draft-rulesets/{draft['id']}/publish")
    assert publish_response.status_code == 200
    ruleset_id = publish_response.json()["id"]

    task_response = client.post(
        "/api/check-tasks",
        json={"document_id": document_id, "ruleset_id": ruleset_id},
    )
    assert task_response.status_code == 200
    task = task_response.json()
    assert task["status"] == "succeeded"
    assert task["report_id"]

    history_response = client.get("/api/check-tasks")
    assert history_response.status_code == 200
    assert any(item["id"] == task["id"] for item in history_response.json())


def test_upload_document_accepts_doc_after_conversion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "prepare_word_document", _fake_prepare_doc_upload)
    client = TestClient(app)

    document_response = client.post(
        "/api/documents",
        files={"file": ("paper.doc", b"legacy word content", "application/msword")},
    )

    assert document_response.status_code == 200
    payload = document_response.json()
    assert payload["filename"] == "paper.doc"
    assert payload["original_format"] == "doc"
    assert payload["normalized_format"] == "docx"
    assert main.DOCUMENTS[payload["document_id"]]["path"].endswith(".docx")


def test_upload_requirement_document_accepts_doc_after_conversion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main, "prepare_word_document", _fake_prepare_doc_upload)
    client = TestClient(app)

    requirement_response = client.post(
        "/api/requirement-documents",
        files={"file": ("rules.doc", b"legacy word content", "application/msword")},
    )

    assert requirement_response.status_code == 200
    payload = requirement_response.json()
    assert payload["filename"] == "rules.doc"
    assert payload["path"].endswith(".docx")
    assert payload["original_format"] == "doc"
    assert payload["normalized_format"] == "docx"
    assert "正文内容" in payload["extracted_text"]
