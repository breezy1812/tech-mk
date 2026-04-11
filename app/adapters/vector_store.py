from pathlib import Path

from pydantic import TypeAdapter

from app.domain.schemas.rag import ChunkRecord, IndexManifest, IndexingReport, RetrievedChunk


class ChromaVectorStore:
    def __init__(self, persist_path: str, collection_name: str) -> None:
        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError("chromadb is required for RAG indexing") from exc

        self._persist_dir = Path(persist_path)
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._report_path = self._persist_dir / "indexing_report.json"
        self._manifest_path = self._persist_dir / "indexing_manifest.json"
        self._client = chromadb.PersistentClient(path=str(self._persist_dir))
        self.collection_name = collection_name
        self._collection = self._client.get_or_create_collection(name=collection_name)

    def reset_collection(self) -> None:
        try:
            self._client.delete_collection(self.collection_name)
        except Exception:
            pass
        self._collection = self._client.get_or_create_collection(name=self.collection_name)

    def upsert(self, chunks: list[ChunkRecord], embeddings: list[list[float]]) -> None:
        if not chunks:
            return
        self._collection.upsert(
            ids=[chunk.chunk_id for chunk in chunks],
            documents=[chunk.content for chunk in chunks],
            metadatas=[
                {
                    "file_name": chunk.file_name,
                    "relative_path": chunk.relative_path,
                    "source_type": chunk.source_type,
                    "chunk_index": chunk.chunk_index,
                    "content_hash": chunk.content_hash,
                }
                for chunk in chunks
            ],
            embeddings=embeddings,
        )

    def delete(self, chunk_ids: list[str]) -> None:
        if not chunk_ids:
            return
        self._collection.delete(ids=chunk_ids)

    def stats(self) -> tuple[int, int]:
        count = self._collection.count()
        if count == 0:
            return 0, 0
        payload = self._collection.get(include=["metadatas"])
        metadatas = payload.get("metadatas", [])
        indexed_files = len({metadata.get("relative_path") for metadata in metadatas if metadata})
        return indexed_files, count

    def query(self, embedding: list[float], top_k: int) -> list[RetrievedChunk]:
        result = self._collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        documents = result.get("documents") or [[]]
        metadatas = result.get("metadatas") or [[]]
        distances = result.get("distances") or [[]]
        if not documents or not documents[0]:
            return []

        records: list[RetrievedChunk] = []

        for document, metadata, distance in zip(documents[0], metadatas[0], distances[0]):
            relevance_score = 1.0 / (1.0 + float(distance))
            records.append(
                RetrievedChunk(
                    file=str(metadata.get("file_name", "unknown")),
                    chunk=int(metadata.get("chunk_index", 0)),
                    relative_path=str(metadata.get("relative_path", "unknown")),
                    content=str(document),
                    score=relevance_score,
                )
            )

        records.sort(key=lambda item: item.score or 0.0, reverse=True)
        return records

    def save_report(self, report: IndexingReport) -> None:
        self._report_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    def load_report(self) -> IndexingReport | None:
        if not self._report_path.exists():
            return None
        return TypeAdapter(IndexingReport).validate_json(self._report_path.read_text(encoding="utf-8"))

    def save_manifest(self, manifest: IndexManifest) -> None:
        self._manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

    def load_manifest(self) -> IndexManifest | None:
        if not self._manifest_path.exists():
            return None
        return TypeAdapter(IndexManifest).validate_json(self._manifest_path.read_text(encoding="utf-8"))
