import logging
from hashlib import sha256
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.adapters.embedding_client import EmbeddingClient
from app.adapters.vector_store import ChromaVectorStore
from app.config import settings
from app.domain.schemas.rag import IndexManifest, IndexManifestFile, IndexingFileReport, IndexingReport, RAGStatusResponse
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
        return self._index_documents(mode="reindex", reset_collection=True)

    def sync_index(self) -> IndexingReport:
        manifest = self.vector_store.load_manifest()
        indexed_files, indexed_chunks = self.vector_store.stats()
        if manifest is None:
            if indexed_chunks > 0:
                logger.info("No indexing manifest found for existing collection; falling back to full rebuild.")
                return self._index_documents(mode="reindex", reset_collection=True)
        elif manifest.docs_root != str(self.docs_root) or len(manifest.files) != indexed_files:
            logger.info(
                "Index manifest is inconsistent with current docs root or collection stats; falling back to full rebuild."
            )
            return self._index_documents(mode="reindex", reset_collection=True)
        return self._index_documents(mode="sync", reset_collection=False, manifest=manifest)

    def _index_documents(
        self,
        mode: str,
        reset_collection: bool,
        manifest: IndexManifest | None = None,
    ) -> IndexingReport:
        files = sorted(path for path in self.docs_root.rglob("*") if path.is_file())
        supported_files = [path for path in files if self.loader_registry.supports(path)]
        if reset_collection:
            self.vector_store.reset_collection()

        existing_manifest_files = {}
        if manifest is not None:
            existing_manifest_files = {item.relative_path: item for item in manifest.files}

        next_manifest_files: dict[str, IndexManifestFile] = {}
        report_files: list[IndexingFileReport] = []
        failed_files: list[str] = []
        total_chunks = 0
        files_indexed = 0
        files_unchanged = 0
        files_deleted = 0
        active_paths: set[str] = set()

        for path in supported_files:
            relative_path = path.relative_to(self.docs_root).as_posix()
            active_paths.add(relative_path)
            file_hash = self._compute_file_hash(path)
            last_modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            existing_file = existing_manifest_files.get(relative_path)

            if mode == "sync" and existing_file is not None and existing_file.file_hash == file_hash:
                next_manifest_files[relative_path] = existing_file.model_copy(update={"last_modified_at": last_modified_at})
                files_unchanged += 1
                report_files.append(
                    IndexingFileReport(
                        file=path.name,
                        relative_path=relative_path,
                        chunk_count=existing_file.chunk_count,
                        status="unchanged",
                    )
                )
                continue

            try:
                document = self.loader_registry.load(path, self.docs_root)
                chunks = self.chunker.chunk_document(document)
                embeddings = [self.embedding_client.embed(chunk.content) for chunk in chunks]
                self.vector_store.upsert(chunks, embeddings)

                if existing_file is not None:
                    new_chunk_ids = {chunk.chunk_id for chunk in chunks}
                    stale_chunk_ids = [chunk_id for chunk_id in existing_file.chunk_ids if chunk_id not in new_chunk_ids]
                    self.vector_store.delete(stale_chunk_ids)

                total_chunks += len(chunks)
                files_indexed += 1
                next_manifest_files[relative_path] = IndexManifestFile(
                    file=path.name,
                    relative_path=relative_path,
                    source_type=document.source_type,
                    file_hash=file_hash,
                    last_modified_at=last_modified_at,
                    chunk_ids=[chunk.chunk_id for chunk in chunks],
                    chunk_count=len(chunks),
                )
                report_files.append(
                    IndexingFileReport(
                        file=path.name,
                        relative_path=relative_path,
                        chunk_count=len(chunks),
                        status="updated" if existing_file is not None and mode == "sync" else "indexed",
                    )
                )
            except Exception as exc:
                logger.exception("Failed to index %s: %s", relative_path, exc)
                failed_files.append(relative_path)
                if existing_file is not None:
                    next_manifest_files[relative_path] = existing_file
                report_files.append(
                    IndexingFileReport(
                        file=path.name,
                        relative_path=relative_path,
                        chunk_count=0,
                        status="failed",
                        error=str(exc),
                    )
                )

        if not reset_collection:
            deleted_paths = sorted(set(existing_manifest_files) - active_paths)
            for relative_path in deleted_paths:
                deleted_file = existing_manifest_files[relative_path]
                self.vector_store.delete(deleted_file.chunk_ids)
                files_deleted += 1
                report_files.append(
                    IndexingFileReport(
                        file=deleted_file.file,
                        relative_path=relative_path,
                        chunk_count=0,
                        status="deleted",
                    )
                )

        indexed_at = datetime.now(timezone.utc)
        saved_manifest = IndexManifest(
            collection_name=settings.rag_collection_name,
            docs_root=str(self.docs_root),
            updated_at=indexed_at,
            files=list(next_manifest_files.values()),
        )

        report = IndexingReport(
            mode=mode,
            collection_name=settings.rag_collection_name,
            embedding_model=self.embedding_client.model_name,
            docs_root=str(self.docs_root),
            files_processed=len(supported_files),
            chunks_indexed=total_chunks,
            files_indexed=files_indexed,
            files_unchanged=files_unchanged,
            files_deleted=files_deleted,
            files=report_files,
            failed_files=failed_files,
            indexed_at=indexed_at,
        )
        self.vector_store.save_manifest(saved_manifest)
        self.vector_store.save_report(report)
        return report

    def _compute_file_hash(self, path: Path) -> str:
        digest = sha256()
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(65536)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

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
