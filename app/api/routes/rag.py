from fastapi import APIRouter, HTTPException

from app.config import settings
from app.domain.schemas.rag import IndexingReport, RAGQueryRequest, RAGQueryResponse, RAGStatusResponse
from app.services.indexing_service import IndexingService
from app.services.rag_service import RAGBackendError, RAGService


def build_rag_router(indexing_service: IndexingService, rag_service: RAGService) -> APIRouter:
    router = APIRouter(prefix="/rag", tags=["rag"])

    @router.get("/status", response_model=RAGStatusResponse)
    def rag_status() -> RAGStatusResponse:
        return indexing_service.status()

    @router.post("/reindex", response_model=IndexingReport)
    def rag_reindex() -> IndexingReport:
        if not settings.rag_allow_reindex:
            raise HTTPException(status_code=403, detail="RAG reindex is disabled")
        return indexing_service.reindex()

    @router.post("/sync", response_model=IndexingReport)
    def rag_sync() -> IndexingReport:
        if not settings.rag_allow_reindex:
            raise HTTPException(status_code=403, detail="RAG sync is disabled")
        return indexing_service.sync_index()

    @router.post("/query", response_model=RAGQueryResponse)
    def rag_query(request: RAGQueryRequest) -> RAGQueryResponse:
        try:
            return rag_service.query(
                question=request.question,
                top_k=request.top_k,
                debug=request.debug,
            )
        except RAGBackendError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return router
