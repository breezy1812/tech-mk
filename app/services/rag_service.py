import logging
import uuid

from app.adapters.ollama_client import OllamaClient, OllamaUnavailableError
from app.config import settings
from app.domain.schemas.rag import ChunkSource, RAGQueryResponse, RetrievedChunk
from app.rag_trace import archive_trace_event
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
        trace_id = uuid.uuid4().hex[:8]
        logger.info(
            "[trace %s] RAG query start top_k=%s debug=%s question=%s",
            trace_id,
            top_k or settings.rag_top_k,
            effective_debug,
            question,
        )
        archive_trace_event(
            trace_id,
            "query_start",
            {
                "question": question,
                "top_k": top_k or settings.rag_top_k,
                "debug": effective_debug,
            },
        )

        try:
            retrieved_chunks = self.retrieval_service.retrieve(question=question, top_k=top_k, trace_id=trace_id)
        except Exception as exc:
            logger.exception("[trace %s] Retrieval failed for question=%s", trace_id, question)
            archive_trace_event(trace_id, "retrieval_failed", {"question": question, "error": str(exc)})
            raise RAGBackendError("Failed to retrieve relevant knowledge base chunks") from exc

        if not retrieved_chunks:
            logger.info("[trace %s] No chunks retrieved", trace_id)
            archive_trace_event(trace_id, "no_chunks", {"question": question})
            return RAGQueryResponse(
                answer="目前知識庫中沒有足夠資訊可以回答這個問題。",
                sources=[],
                retrieved_chunks=[] if effective_debug else None,
            )

        prompt = self.prompt_builder.build_prompt(question=question, chunks=retrieved_chunks)
        logger.info(
            "[trace %s] Built prompt with %d chunks and %d chars",
            trace_id,
            len(retrieved_chunks),
            len(prompt),
        )
        archive_trace_event(
            trace_id,
            "prompt_built",
            {
                "chunk_count": len(retrieved_chunks),
                "prompt_chars": len(prompt),
                "sources": [chunk.file for chunk in retrieved_chunks],
            },
        )
        try:
            result = self.client.chat(prompt)
        except OllamaUnavailableError as exc:
            logger.exception("[trace %s] Ollama generation failed", trace_id)
            archive_trace_event(trace_id, "generation_failed", {"error": str(exc)})
            raise RAGBackendError("Failed to generate RAG answer from Ollama") from exc

        sources = self._build_sources(retrieved_chunks)
        logger.info(
            "[trace %s] Final sources=%s answer_preview=%s",
            trace_id,
            [source.file for source in sources],
            self._preview_text(result["reply"]),
        )
        archive_trace_event(
            trace_id,
            "answer_generated",
            {
                "sources": [source.file for source in sources],
                "answer_preview": self._preview_text(result["reply"]),
            },
        )
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

    def _preview_text(self, text: str, limit: int = 120) -> str:
        compact = " ".join(text.split())
        if len(compact) <= limit:
            return compact
        return f"{compact[:limit]}..."
