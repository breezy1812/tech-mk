from fastapi import APIRouter

from app.domain.schemas.chat import ChatRequest, ChatResponse, NormalizedMessage
from app.services.chat_service import ChatService


def build_chat_router(chat_service: ChatService) -> APIRouter:
    router = APIRouter()

    @router.post("/chat", response_model=ChatResponse)
    def chat(request: ChatRequest) -> ChatResponse:
        message = NormalizedMessage(
            source=request.source,
            user_id=request.user_id or "api-user",
            chat_id="api-chat",
            text=request.text,
            raw=request.model_dump(),
        )
        return chat_service.handle_message(message)

    return router
