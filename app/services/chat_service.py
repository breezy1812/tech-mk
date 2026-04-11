from app.adapters.ollama_client import OllamaClient
from app.domain.schemas.chat import ChatResponse, NormalizedMessage
from app.router import MessageRouter


class ChatService:
    def __init__(self) -> None:
        self.router = MessageRouter()
        self.client = OllamaClient()

    def handle_message(self, message: NormalizedMessage) -> ChatResponse:
        prompt = self.router.build_prompt(message)
        result = self.client.chat(prompt)
        return ChatResponse(reply=result["reply"], model=result["model"])
