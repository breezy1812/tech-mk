from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.config import settings
from app.domain.schemas.rag import ChunkSource, IndexingFileReport, IndexingReport, RAGQueryResponse, RAGStatusResponse, RetrievedChunk
from app.main import app, indexing_service, rag_service
from app.services.rag_service import RAGBackendError

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


def test_rag_sync_requires_flag() -> None:
    original_allow_reindex = settings.rag_allow_reindex
    try:
        settings.rag_allow_reindex = False
        response = client.post("/rag/sync")
        assert response.status_code == 403
    finally:
        settings.rag_allow_reindex = original_allow_reindex


def test_rag_sync_returns_indexing_report(monkeypatch) -> None:
    report = IndexingReport(
        mode="sync",
        collection_name="tech_docs",
        embedding_model="fake-embed",
        docs_root="data/docs",
        files_processed=2,
        chunks_indexed=3,
        files_indexed=1,
        files_unchanged=1,
        files_deleted=1,
        files=[
            IndexingFileReport(
                file="guide.md",
                relative_path="guide.md",
                chunk_count=3,
                status="updated",
            ),
            IndexingFileReport(
                file="old.txt",
                relative_path="old.txt",
                chunk_count=0,
                status="deleted",
            ),
        ],
        failed_files=[],
        indexed_at=datetime.now(timezone.utc),
    )
    original_allow_reindex = settings.rag_allow_reindex

    try:
        settings.rag_allow_reindex = True
        monkeypatch.setattr(indexing_service, "sync_index", lambda: report)

        response = client.post("/rag/sync")

        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "sync"
        assert data["files_indexed"] == 1
        assert data["files_deleted"] == 1
        assert data["files"][1]["status"] == "deleted"
    finally:
        settings.rag_allow_reindex = original_allow_reindex


def test_rag_query_returns_answer_and_sources(monkeypatch) -> None:
    payload = RAGQueryResponse(
        answer="RAG uses retrieved context.",
        sources=[ChunkSource(file="guide.md", chunk=0, relative_path="guide.md")],
        retrieved_chunks=[
            RetrievedChunk(file="guide.md", chunk=0, relative_path="guide.md", content="RAG uses context", score=0.9)
        ],
    )
    monkeypatch.setattr(rag_service, "query", lambda question, top_k, debug: payload)

    response = client.post("/rag/query", json={"question": "What is RAG?", "top_k": 2, "debug": True})

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "RAG uses retrieved context."
    assert data["sources"][0]["file"] == "guide.md"
    assert data["retrieved_chunks"][0]["score"] == 0.9


def test_rag_query_returns_backend_failure(monkeypatch) -> None:
    def fail(question, top_k, debug):
        raise RAGBackendError("retrieval backend failed")

    monkeypatch.setattr(rag_service, "query", fail)

    response = client.post("/rag/query", json={"question": "What is RAG?"})

    assert response.status_code == 502
    assert response.json()["detail"] == "retrieval backend failed"