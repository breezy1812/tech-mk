import logging
from typing import Any, Dict

import requests
from fastapi import FastAPI, HTTPException

from app.config import settings
from app.connectors.discord_handler import DiscordParser
from app.connectors.telegram_handler import TelegramParser
from app.logging_setup import setup_logging
from app.models import ChatRequest, ChatResponse, NormalizedMessage
from app.service import ChatService

setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)
service = ChatService()


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}


@app.get("/config/check")
def config_check() -> Dict[str, Any]:
    return {
        "ollama_base_url": settings.ollama_base_url,
        "ollama_model": settings.ollama_model,
        "telegram_configured": bool(settings.telegram_bot_token),
        "discord_configured": bool(settings.discord_bot_token),
        "app_base_url": settings.app_base_url,
    }


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
    message = TelegramParser.parse(payload)
    if message is None:
        return {"ok": True, "skipped": True}

    response = service.handle_message(message)
    _send_telegram_reply(chat_id=message.chat_id, text=response.reply)
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


def _send_telegram_reply(chat_id: str, text: str) -> None:
    if not settings.telegram_bot_token:
        logger.warning("Telegram token is empty; skip sending reply.")
        return

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}

    try:
        response = requests.post(url, json=payload, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.exception("Failed to send Telegram message: %s", exc)
        raise HTTPException(status_code=502, detail="Telegram reply failed") from exc
