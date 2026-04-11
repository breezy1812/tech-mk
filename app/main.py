import logging
from typing import Any, Dict

from fastapi import FastAPI

from app.config import settings
from app.connectors.discord_handler import DiscordParser
from app.connectors.telegram_handler import TelegramParser
from app.logging_setup import setup_logging
from app.models import ChatRequest, ChatResponse, NormalizedMessage
from app.service import ChatService
from app.telegram_polling import TelegramBotClient, TelegramPollingWorker, process_telegram_update

setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)
service = ChatService()
telegram_client = TelegramBotClient()
telegram_poller = TelegramPollingWorker(service=service, bot_client=telegram_client)


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}


@app.get("/config/check")
def config_check() -> Dict[str, Any]:
    return {
        "ollama_base_url": settings.ollama_base_url,
        "ollama_model": settings.ollama_model,
        "telegram_configured": bool(settings.telegram_bot_token),
        "telegram_polling_enabled": settings.telegram_polling_enabled,
        "discord_configured": bool(settings.discord_bot_token),
        "app_base_url": settings.app_base_url,
    }


@app.on_event("startup")
def startup_event() -> None:
    telegram_poller.start()


@app.on_event("shutdown")
def shutdown_event() -> None:
    telegram_poller.stop()


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    message = NormalizedMessage(
        source=request.source,
        user_id=request.user_id or "api-user",
        chat_id="api-chat",
        text=request.text,
        raw=request.model_dump(),
    )
    return service.handle_message(message)


@app.post("/webhook/telegram")
def telegram_webhook(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not process_telegram_update(payload, service=service, bot_client=telegram_client):
        return {"ok": True, "skipped": True}
    return {"ok": True}


@app.post("/webhook/discord")
def discord_webhook(payload: Dict[str, Any]) -> Dict[str, Any]:
    if payload.get("type") == 1:
        return {"type": 1}

    message = DiscordParser.parse(payload)
    if message is None:
        return {"ok": True, "skipped": True}

    response = service.handle_message(message)
    return {
        "ok": True,
        "reply": response.reply,
        "model": response.model,
    }
