from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient

from docchecker.api import main
from docchecker.api.main import app
from docchecker.services.file_storage import LocalFileStorage
from docchecker.services.state_store import SqliteStateStore
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


@pytest.fixture(autouse=True)
def isolate_api_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = SqliteStateStore(tmp_path / "docchecker.sqlite3")
    store.initialize()
    monkeypatch.setattr(main, "state_store", store)
    monkeypatch.setattr(main, "storage", LocalFileStorage(tmp_path / "storage"))


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

    restarted_store = SqliteStateStore(main.state_store.path)
    restarted_store.initialize()
    main.state_store = restarted_store

    restarted_history_response = client.get("/api/check-tasks")
    assert restarted_history_response.status_code == 200
    assert any(item["id"] == task["id"] for item in restarted_history_response.json())

    restarted_task_response = client.get(f"/api/check-tasks/{task['id']}")
    assert restarted_task_response.status_code == 200
    assert restarted_task_response.json()["report_id"] == task["report_id"]

    report_response = client.get(f"/api/reports/{task['report_id']}")
    assert report_response.status_code == 200
    assert report_response.json()["id"] == task["report_id"]

    draft_response = client.get(f"/api/draft-rulesets/{draft['id']}")
    assert draft_response.status_code == 200
    assert draft_response.json()["status"] == "published"

    rulesets_response = client.get("/api/rulesets")
    assert rulesets_response.status_code == 200
    assert any(item["id"] == ruleset_id for item in rulesets_response.json())

    rename_response = client.patch(
        f"/api/rulesets/{ruleset_id}",
        json={"name": "学校论文格式模板"},
    )
    assert rename_response.status_code == 200
    renamed_ruleset = rename_response.json()
    assert renamed_ruleset["name"] == "学校论文格式模板"
    assert renamed_ruleset["rules"]

    main.state_store = SqliteStateStore(main.state_store.path)
    main.state_store.initialize()
    renamed_list_response = client.get("/api/rulesets")
    assert renamed_list_response.status_code == 200
    assert any(
        item["id"] == ruleset_id and item["name"] == "学校论文格式模板"
        for item in renamed_list_response.json()
    )

    delete_task_response = client.delete(f"/api/check-tasks/{task['id']}")
    assert delete_task_response.status_code == 200
    assert delete_task_response.json() == {"id": task["id"], "deleted": True}
    assert client.get(f"/api/check-tasks/{task['id']}").status_code == 404
    assert client.get(f"/api/reports/{task['report_id']}").status_code == 404
    assert not main.storage.report_path(task["report_id"]).exists()

    delete_ruleset_response = client.delete(f"/api/rulesets/{ruleset_id}")
    assert delete_ruleset_response.status_code == 200
    assert delete_ruleset_response.json() == {"id": ruleset_id, "deleted": True}
    assert not any(item["id"] == ruleset_id for item in client.get("/api/rulesets").json())
    assert client.delete(f"/api/rulesets/{ruleset_id}").status_code == 404
    assert client.delete(f"/api/check-tasks/{task['id']}").status_code == 404


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
    document = main.state_store.get_document(payload["document_id"])
    assert document is not None
    assert document.path.endswith(".docx")


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


def test_upload_document_cleans_file_when_persistence_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingStore:
        def save_document(self, document) -> None:
            raise RuntimeError("database unavailable")

    docx_path = tmp_path / "paper.docx"
    _create_docx(docx_path, "正文内容")
    monkeypatch.setattr(main, "state_store", FailingStore())
    client = TestClient(app, raise_server_exceptions=False)

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

    assert document_response.status_code == 500
    assert list(main.storage.documents_dir.iterdir()) == []
