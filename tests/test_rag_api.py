from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.config import settings
from app.domain.schemas.rag import IndexingFileReport, IndexingReport, RAGStatusResponse
from app.main import app, indexing_service

client = TestClient(app)


def test_rag_status_returns_service_payload(monkeypatch) -> None:
    payload = RAGStatusResponse(
        enabled=True,
        collection_name="tech_docs",
        embedding_model="fake-embed",
        docs_root="data/docs",
        chunk_size=800,
        chunk_overlap=120,
        indexed_files=2,
        indexed_chunks=5,
        last_indexed_at=datetime.now(timezone.utc),
        last_report=None,
    )

    monkeypatch.setattr(indexing_service, "status", lambda: payload)

    response = client.get("/rag/status")

    assert response.status_code == 200
    data = response.json()
    assert data["collection_name"] == "tech_docs"
    assert data["indexed_chunks"] == 5


def test_rag_reindex_requires_flag() -> None:
    original_allow_reindex = settings.rag_allow_reindex
    try:
        settings.rag_allow_reindex = False
        response = client.post("/rag/reindex")
        assert response.status_code == 403
    finally:
        settings.rag_allow_reindex = original_allow_reindex


def test_rag_reindex_returns_indexing_report(monkeypatch) -> None:
    report = IndexingReport(
        collection_name="tech_docs",
        embedding_model="fake-embed",
        docs_root="data/docs",
        files_processed=1,
        chunks_indexed=3,
        files=[
            IndexingFileReport(
                file="guide.md",
                relative_path="guide.md",
                chunk_count=3,
                status="indexed",
            )
        ],
        failed_files=[],
        indexed_at=datetime.now(timezone.utc),
    )
    original_allow_reindex = settings.rag_allow_reindex

    try:
        settings.rag_allow_reindex = True
        monkeypatch.setattr(indexing_service, "reindex", lambda: report)

        response = client.post("/rag/reindex")

        assert response.status_code == 200
        data = response.json()
        assert data["collection_name"] == "tech_docs"
        assert data["chunks_indexed"] == 3
        assert data["files"][0]["file"] == "guide.md"
    finally:
        settings.rag_allow_reindex = original_allow_reindex