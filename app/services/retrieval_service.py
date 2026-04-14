import logging
import re
from typing import Optional

from app.adapters.embedding_client import EmbeddingClient
from app.adapters.vector_store import ChromaVectorStore
from app.config import settings
from app.domain.schemas.rag import RetrievedChunk
from app.rag_trace import archive_trace_event


logger = logging.getLogger(__name__)


class RetrievalService:
    _candidate_multiplier = 4
    _candidate_floor = 12
    _candidate_cap = 24
    _question_stop_terms = {
        "請問",
        "什麼",
        "時候",
        "何時",
        "在哪",
        "哪裡",
        "放在",
        "放哪",
        "是不是",
        "是否",
        "有沒有",
        "內容",
        "資料",
        "做的",
        "的是",
    }
    _question_split_pattern = re.compile(
        r"請問|什麼時候|何時|在哪裡|在哪|放在哪裡|放哪裡|放在哪|是不是|是否|有沒有|做的|的是|的|是|了|嗎"
    )

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

    def retrieve(self, question: str, top_k: int | None = None, trace_id: str | None = None) -> list[RetrievedChunk]:
        effective_top_k = top_k or settings.rag_top_k
        query_embedding = self.embedding_client.embed(question)
        candidate_k = min(
            max(effective_top_k * self._candidate_multiplier, self._candidate_floor),
            self._candidate_cap,
        )
        candidates = self.vector_store.query(query_embedding, max(effective_top_k, candidate_k))
        query_terms = self._extract_query_terms(question)
        logger.info(
            "[trace %s] Retrieved %d candidates with top_k=%d candidate_k=%d query_terms=%s",
            trace_id or "-",
            len(candidates),
            effective_top_k,
            candidate_k,
            query_terms[:12],
        )
        archive_trace_event(
            trace_id or "-",
            "retrieved_candidates",
            {
                "top_k": effective_top_k,
                "candidate_k": candidate_k,
                "query_terms": query_terms[:20],
                "candidates": self._summarize_chunks(candidates),
            },
        )
        logger.info(
            "[trace %s] Candidate preview: %s",
            trace_id or "-",
            self._summarize_chunks(candidates),
        )
        ranked = self._rerank(chunks=candidates, top_k=effective_top_k, query_terms=query_terms)
        logger.info(
            "[trace %s] Reranked top chunks: %s",
            trace_id or "-",
            self._summarize_chunks(ranked),
        )
        archive_trace_event(
            trace_id or "-",
            "reranked_chunks",
            {
                "top_k": effective_top_k,
                "chunks": self._summarize_chunks(ranked),
            },
        )
        return ranked

    def _rerank(self, chunks: list[RetrievedChunk], top_k: int, query_terms: list[str]) -> list[RetrievedChunk]:
        if not chunks:
            return []

        if not query_terms:
            return chunks[:top_k]

        ranked = sorted(
            chunks,
            key=lambda chunk: self._score_chunk(chunk, query_terms),
            reverse=True,
        )
        return ranked[:top_k]

    def _score_chunk(self, chunk: RetrievedChunk, query_terms: list[str]) -> tuple[float, float]:
        haystack = f"{chunk.file}\n{chunk.relative_path}\n{chunk.content}".lower()
        file_haystack = f"{chunk.file}\n{chunk.relative_path}".lower()
        keyword_score = 0.0

        for term in query_terms:
            lowered = term.lower()
            length_bonus = min(len(term), 6)
            if lowered in file_haystack:
                keyword_score += 8.0 + length_bonus
            if lowered in haystack:
                occurrences = haystack.count(lowered)
                keyword_score += 2.0 + min(occurrences, 3) * (1.0 + length_bonus * 0.2)

        semantic_score = float(chunk.score or 0.0)
        return (keyword_score, semantic_score)

    def _extract_query_terms(self, question: str) -> list[str]:
        normalized = question.strip().lower()
        if not normalized:
            return []

        ascii_terms = {
            match.group(0)
            for match in re.finditer(r"[a-z0-9][a-z0-9._:-]{1,}", normalized)
        }

        cjk_terms: set[str] = set()
        compact = re.sub(r"\s+", "", normalized)
        for match in re.finditer(r"[\u4e00-\u9fff0-9]{2,}", compact):
            token = match.group(0)
            pieces = [piece for piece in self._question_split_pattern.split(token) if len(piece) >= 2]
            for piece in pieces:
                if piece in self._question_stop_terms:
                    continue
                cjk_terms.add(piece)
                max_size = min(6, len(piece))
                for size in range(2, max_size + 1):
                    for start in range(0, len(piece) - size + 1):
                        subpiece = piece[start : start + size]
                        if subpiece not in self._question_stop_terms:
                            cjk_terms.add(subpiece)

        combined = ascii_terms | cjk_terms
        return sorted(combined, key=lambda item: (-len(item), item))

    def _summarize_chunks(self, chunks: list[RetrievedChunk]) -> list[dict[str, object]]:
        preview: list[dict[str, object]] = []
        for chunk in chunks[:8]:
            preview.append(
                {
                    "file": chunk.file,
                    "chunk": chunk.chunk,
                    "score": round(float(chunk.score or 0.0), 4),
                }
            )
        return preview
