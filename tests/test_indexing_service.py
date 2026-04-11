from datetime import datetime, timezone

from app.config import settings
from app.domain.schemas.rag import IndexManifest, IndexManifestFile, IndexingReport
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
        self.saved_manifest = None
        self.loaded_manifest = None
        self.deleted_ids = []

    def reset_collection(self) -> None:
        self.reset_called = True

    def upsert(self, chunks, embeddings) -> None:
        self.upserts.append((chunks, embeddings))

    def stats(self) -> tuple[int, int]:
        chunk_count = sum(len(chunks) for chunks, _ in self.upserts)
        return len(self.upserts), chunk_count

    def delete(self, chunk_ids) -> None:
        self.deleted_ids.append(list(chunk_ids))

    def save_report(self, report: IndexingReport) -> None:
        self.saved_report = report

    def save_manifest(self, manifest: IndexManifest) -> None:
        self.saved_manifest = manifest

    def load_report(self):
        return self.saved_report

    def load_manifest(self):
        return self.loaded_manifest


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


def test_sync_index_only_updates_changed_files_and_deletes_missing_files(tmp_path) -> None:
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    (docs_root / "guide.md").write_text("# Title\n\nnew content", encoding="utf-8")

    original_docs_root = settings.rag_docs_root
    original_vector_store_path = settings.rag_vector_store_path
    try:
        settings.rag_docs_root = str(docs_root)
        settings.rag_vector_store_path = str(tmp_path / "vector_store")
        service = IndexingService()
        service._embedding_client = FakeEmbeddingClient()
        service._vector_store = FakeVectorStore()
        service._vector_store.loaded_manifest = IndexManifest(
            collection_name=settings.rag_collection_name,
            docs_root=str(docs_root),
            updated_at=datetime.now(timezone.utc),
            files=[
                IndexManifestFile(
                    file="guide.md",
                    relative_path="guide.md",
                    source_type="markdown",
                    file_hash="old-hash",
                    last_modified_at=datetime.now(timezone.utc),
                    chunk_ids=["guide.md:0", "guide.md:1"],
                    chunk_count=2,
                ),
                IndexManifestFile(
                    file="old.txt",
                    relative_path="old.txt",
                    source_type="text",
                    file_hash="gone-hash",
                    last_modified_at=datetime.now(timezone.utc),
                    chunk_ids=["old.txt:0"],
                    chunk_count=1,
                ),
            ],
        )

        report = service.sync_index()

        assert report.mode == "sync"
        assert report.files_processed == 1
        assert report.files_indexed == 1
        assert report.files_deleted == 1
        assert report.files_unchanged == 0
        assert any(item.relative_path == "guide.md" and item.status == "updated" for item in report.files)
        assert any(item.relative_path == "old.txt" and item.status == "deleted" for item in report.files)
        assert service.vector_store.deleted_ids == [["guide.md:1"], ["old.txt:0"]]
        assert service.vector_store.saved_manifest is not None
        assert [item.relative_path for item in service.vector_store.saved_manifest.files] == ["guide.md"]
    finally:
        settings.rag_docs_root = original_docs_root
        settings.rag_vector_store_path = original_vector_store_path


def test_sync_index_marks_unchanged_files_without_reembedding(tmp_path) -> None:
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    file_path = docs_root / "notes.txt"
    file_path.write_text("same content", encoding="utf-8")

    original_docs_root = settings.rag_docs_root
    original_vector_store_path = settings.rag_vector_store_path
    try:
        settings.rag_docs_root = str(docs_root)
        settings.rag_vector_store_path = str(tmp_path / "vector_store")
        service = IndexingService()
        service._embedding_client = FakeEmbeddingClient()
        service._vector_store = FakeVectorStore()
        service._vector_store.loaded_manifest = IndexManifest(
            collection_name=settings.rag_collection_name,
            docs_root=str(docs_root),
            updated_at=datetime.now(timezone.utc),
            files=[
                IndexManifestFile(
                    file="notes.txt",
                    relative_path="notes.txt",
                    source_type="text",
                    file_hash=service._compute_file_hash(file_path),
                    last_modified_at=datetime.now(timezone.utc),
                    chunk_ids=["notes.txt:0"],
                    chunk_count=1,
                )
            ],
        )

        report = service.sync_index()

        assert report.mode == "sync"
        assert report.files_indexed == 0
        assert report.files_unchanged == 1
        assert report.files_deleted == 0
        assert report.chunks_indexed == 0
        assert service.vector_store.upserts == []
        assert any(item.relative_path == "notes.txt" and item.status == "unchanged" for item in report.files)
    finally:
        settings.rag_docs_root = original_docs_root
        settings.rag_vector_store_path = original_vector_store_path
