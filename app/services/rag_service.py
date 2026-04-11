import logging

from app.adapters.ollama_client import OllamaClient, OllamaUnavailableError
from app.config import settings
from app.domain.schemas.rag import ChunkSource, RAGQueryResponse, RetrievedChunk
from app.services.rag_prompt_builder import RAGPromptBuilder
from app.services.retrieval_service import RetrievalService

logger = logging.getLogger(__name__)


class RAGBackendError(RuntimeError):
    pass


class RAGService:
    def __init__(
        self,
        retrieval_service: RetrievalService | None = None,
        prompt_builder: RAGPromptBuilder | None = None,
        client: OllamaClient | None = None,
    ) -> None:
        self.retrieval_service = retrieval_service or RetrievalService()
        self.prompt_builder = prompt_builder or RAGPromptBuilder()
        self.client = client or OllamaClient()

    def query(self, question: str, top_k: int | None = None, debug: bool | None = None) -> RAGQueryResponse:
        effective_debug = settings.rag_query_debug_default if debug is None else debug

        try:
            retrieved_chunks = self.retrieval_service.retrieve(question=question, top_k=top_k)
        except Exception as exc:
            raise RAGBackendError("Failed to retrieve relevant knowledge base chunks") from exc

        if not retrieved_chunks:
            return RAGQueryResponse(
                answer="目前知識庫中沒有足夠資訊可以回答這個問題。",
                sources=[],
                retrieved_chunks=[] if effective_debug else None,
            )

        prompt = self.prompt_builder.build_prompt(question=question, chunks=retrieved_chunks)
        try:
            result = self.client.chat(prompt)
        except OllamaUnavailableError as exc:
            raise RAGBackendError("Failed to generate RAG answer from Ollama") from exc

        sources = self._build_sources(retrieved_chunks)
        response = RAGQueryResponse(answer=result["reply"], sources=sources)
        if effective_debug:
            response.retrieved_chunks = retrieved_chunks
        return response

    def _build_sources(self, chunks: list[RetrievedChunk]) -> list[ChunkSource]:
        seen: set[tuple[str, int, str]] = set()
        sources: list[ChunkSource] = []
        for chunk in chunks:
            key = (chunk.file, chunk.chunk, chunk.relative_path)
            if key in seen:
                continue
            seen.add(key)
            sources.append(
                ChunkSource(
                    file=chunk.file,
                    chunk=chunk.chunk,
                    relative_path=chunk.relative_path,
                )
            )
        return sources
