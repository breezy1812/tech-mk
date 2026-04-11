from typing import Optional

from app.adapters.embedding_client import EmbeddingClient
from app.adapters.vector_store import ChromaVectorStore
from app.config import settings
from app.domain.schemas.rag import RetrievedChunk


class RetrievalService:
    def __init__(
        self,
        embedding_client: EmbeddingClient | None = None,
        vector_store: ChromaVectorStore | None = None,
    ) -> None:
        self._embedding_client: Optional[EmbeddingClient] = embedding_client
        self._vector_store: Optional[ChromaVectorStore] = vector_store

    @property
    def embedding_client(self) -> EmbeddingClient:
        if self._embedding_client is None:
            self._embedding_client = EmbeddingClient()
        return self._embedding_client

    @property
    def vector_store(self) -> ChromaVectorStore:
        if self._vector_store is not None:
            return self._vector_store
        return ChromaVectorStore(
            persist_path=settings.rag_vector_store_path,
            collection_name=settings.rag_collection_name,
        )

    def retrieve(self, question: str, top_k: int | None = None) -> list[RetrievedChunk]:
        effective_top_k = top_k or settings.rag_top_k
        query_embedding = self.embedding_client.embed(question)
        return self.vector_store.query(query_embedding, effective_top_k)
