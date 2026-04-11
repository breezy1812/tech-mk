import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict

import requests
from fastapi import FastAPI, HTTPException

from app.api.routes.chat import build_chat_router
from app.api.routes.rag import build_rag_router
from app.config import settings
from app.connectors.discord_handler import DiscordParser
from app.logging_setup import setup_logging
from app.service import ChatService
from app.services.indexing_service import IndexingService
from app.telegram_polling import TelegramBotClient, TelegramPollingWorker, process_telegram_update

setup_logging(settings.log_level)
logger = logging.getLogger(__name__)
service = ChatService()
indexing_service = IndexingService()
telegram_client = TelegramBotClient()
telegram_poller = TelegramPollingWorker(service=service, bot_client=telegram_client)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    telegram_poller.start()
    yield
    telegram_poller.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(build_chat_router(service))
app.include_router(build_rag_router(indexing_service))


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}


@app.get("/config/check")
def config_check() -> Dict[str, Any]:
    return {
        "ollama_base_url": settings.ollama_base_url,
        "ollama_model": settings.ollama_model,
        "rag_enabled": settings.rag_enabled,
        "rag_docs_root": settings.rag_docs_root,
        "rag_collection_name": settings.rag_collection_name,
        "telegram_configured": bool(settings.telegram_bot_token),
        "telegram_polling_enabled": settings.telegram_polling_enabled,
        "discord_configured": bool(settings.discord_bot_token),
        "app_base_url": settings.app_base_url,
    }


@app.post("/webhook/telegram")
def telegram_webhook(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if not process_telegram_update(payload, service=service, bot_client=telegram_client):
            return {"ok": True, "skipped": True}
        return {"ok": True}
    except requests.RequestException as exc:
        logger.exception("Failed to handle Telegram webhook: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to process Telegram webhook") from exc
    except Exception as exc:
        logger.exception("Failed to process Telegram webhook: %s", exc)
        raise HTTPException(status_code=500, detail="Telegram processing failed") from exc


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
