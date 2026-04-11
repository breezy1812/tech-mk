from fastapi import APIRouter, HTTPException

from app.config import settings
from app.domain.schemas.rag import IndexingReport, RAGStatusResponse
from app.services.indexing_service import IndexingService


def build_rag_router(indexing_service: IndexingService) -> APIRouter:
    router = APIRouter(prefix="/rag", tags=["rag"])

    @router.get("/status", response_model=RAGStatusResponse)
    def rag_status() -> RAGStatusResponse:
        return indexing_service.status()

    @router.post("/reindex", response_model=IndexingReport)
    def rag_reindex() -> IndexingReport:
        if not settings.rag_allow_reindex:
            raise HTTPException(status_code=403, detail="RAG reindex is disabled")
        return indexing_service.reindex()

    return router
