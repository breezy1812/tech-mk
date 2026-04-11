import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.adapters.embedding_client import EmbeddingClient
from app.adapters.vector_store import ChromaVectorStore
from app.config import settings
from app.domain.schemas.rag import IndexingFileReport, IndexingReport, RAGStatusResponse
from app.ingestion.chunkers.text_chunker import TextChunker
from app.ingestion.loaders.registry import DocumentLoaderRegistry

logger = logging.getLogger(__name__)


class IndexingService:
    def __init__(self) -> None:
        self.docs_root = Path(settings.rag_docs_root)
        self.docs_root.mkdir(parents=True, exist_ok=True)
        self.loader_registry = DocumentLoaderRegistry()
        self.chunker = TextChunker(settings.rag_chunk_size, settings.rag_chunk_overlap)
        self._embedding_client: Optional[EmbeddingClient] = None
        self._vector_store: Optional[ChromaVectorStore] = None

    @property
    def embedding_client(self) -> EmbeddingClient:
        if self._embedding_client is None:
            self._embedding_client = EmbeddingClient()
        return self._embedding_client

    @property
    def vector_store(self) -> ChromaVectorStore:
        if self._vector_store is None:
            self._vector_store = ChromaVectorStore(settings.rag_vector_store_path, settings.rag_collection_name)
        return self._vector_store

    def reindex(self) -> IndexingReport:
        files = sorted(path for path in self.docs_root.rglob("*") if path.is_file())
        supported_files = [path for path in files if self.loader_registry.supports(path)]
        self.vector_store.reset_collection()

        report_files: list[IndexingFileReport] = []
        failed_files: list[str] = []
        total_chunks = 0

        for path in supported_files:
            relative_path = path.relative_to(self.docs_root).as_posix()
            try:
                document = self.loader_registry.load(path, self.docs_root)
                chunks = self.chunker.chunk_document(document)
                embeddings = [self.embedding_client.embed(chunk.content) for chunk in chunks]
                self.vector_store.upsert(chunks, embeddings)
                total_chunks += len(chunks)
                report_files.append(
                    IndexingFileReport(
                        file=path.name,
                        relative_path=relative_path,
                        chunk_count=len(chunks),
                        status="indexed",
                    )
                )
            except Exception as exc:
                logger.exception("Failed to index %s: %s", relative_path, exc)
                failed_files.append(relative_path)
                report_files.append(
                    IndexingFileReport(
                        file=path.name,
                        relative_path=relative_path,
                        chunk_count=0,
                        status="failed",
                        error=str(exc),
                    )
                )

        report = IndexingReport(
            collection_name=settings.rag_collection_name,
            embedding_model=self.embedding_client.model_name,
            docs_root=str(self.docs_root),
            files_processed=len(supported_files),
            chunks_indexed=total_chunks,
            files=report_files,
            failed_files=failed_files,
            indexed_at=datetime.now(timezone.utc),
        )
        self.vector_store.save_report(report)
        return report

    def status(self) -> RAGStatusResponse:
        indexed_files, indexed_chunks = self.vector_store.stats()
        last_report = self.vector_store.load_report()
        return RAGStatusResponse(
            enabled=settings.rag_enabled,
            collection_name=settings.rag_collection_name,
            embedding_model=self.embedding_client.model_name,
            docs_root=str(self.docs_root),
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap,
            indexed_files=indexed_files,
            indexed_chunks=indexed_chunks,
            last_indexed_at=last_report.indexed_at if last_report else None,
            last_report=last_report,
        )
