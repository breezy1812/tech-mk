from datetime import datetime, timezone

from app.config import settings
from app.domain.schemas.rag import IndexingReport
from app.services.indexing_service import IndexingService


class FakeEmbeddingClient:
    def __init__(self) -> None:
        self.model_name = "fake-embed"

    def embed(self, text: str) -> list[float]:
        return [float(len(text)), 1.0]


class FakeVectorStore:
    def __init__(self) -> None:
        self.reset_called = False
        self.upserts = []
        self.saved_report = None

    def reset_collection(self) -> None:
        self.reset_called = True

    def upsert(self, chunks, embeddings) -> None:
        self.upserts.append((chunks, embeddings))

    def stats(self) -> tuple[int, int]:
        chunk_count = sum(len(chunks) for chunks, _ in self.upserts)
        return len(self.upserts), chunk_count

    def save_report(self, report: IndexingReport) -> None:
        self.saved_report = report

    def load_report(self):
        return self.saved_report


def test_reindex_builds_report_and_skips_failed_files(tmp_path) -> None:
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    (docs_root / "guide.md").write_text("# Title\n\nAlpha beta gamma\n\nMore content here.", encoding="utf-8")
    (docs_root / "notes.txt").write_text("plain text paragraph\n\nsecond paragraph", encoding="utf-8")
    (docs_root / "broken.pdf").write_bytes(b"not-a-valid-pdf")
    (docs_root / "ignored.csv").write_text("skip,me", encoding="utf-8")

    original_docs_root = settings.rag_docs_root
    original_vector_store_path = settings.rag_vector_store_path
    try:
        settings.rag_docs_root = str(docs_root)
        settings.rag_vector_store_path = str(tmp_path / "vector_store")
        service = IndexingService()
        service._embedding_client = FakeEmbeddingClient()
        service._vector_store = FakeVectorStore()

        report = service.reindex()
        status = service.status()

        assert service.vector_store.reset_called is True
        assert report.collection_name == settings.rag_collection_name
        assert report.embedding_model == "fake-embed"
        assert report.files_processed == 3
        assert report.chunks_indexed > 0
        assert "broken.pdf" in report.failed_files
        assert any(item.file == "guide.md" and item.status == "indexed" for item in report.files)
        assert any(item.file == "broken.pdf" and item.status == "failed" for item in report.files)
        assert status.indexed_chunks == report.chunks_indexed
        assert status.last_report is not None
    finally:
        settings.rag_docs_root = original_docs_root
        settings.rag_vector_store_path = original_vector_store_path
