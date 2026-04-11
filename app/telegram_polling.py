import logging
import threading
from typing import Any, Dict, List, Optional

import requests

from app.config import settings
from app.connectors.telegram_handler import TelegramParser
from app.service import ChatService

logger = logging.getLogger(__name__)
# Keep the HTTP client timeout slightly above Telegram long-polling timeout
# so the local request doesn't expire before Telegram responds.
POLLING_TIMEOUT_BUFFER_SECONDS = 10
MAX_TELEGRAM_HTTP_TIMEOUT_SECONDS = 60
MAX_TELEGRAM_JOIN_TIMEOUT_SECONDS = 60


class TelegramBotClient:
    def __init__(self) -> None:
        self._base_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}"

    def get_updates(self, offset: Optional[int] = None) -> List[Dict[str, Any]]:
        if not settings.telegram_bot_token:
            return []

        payload: Dict[str, Any] = {
            "timeout": settings.telegram_polling_timeout_seconds,
            "limit": settings.telegram_polling_limit,
        }
        if offset is not None:
            payload["offset"] = offset

        response = requests.get(
            f"{self._base_url}/getUpdates",
            params=payload,
            timeout=min(
                settings.telegram_polling_timeout_seconds + POLLING_TIMEOUT_BUFFER_SECONDS,
                MAX_TELEGRAM_HTTP_TIMEOUT_SECONDS,
            ),
        )
        response.raise_for_status()

        data = response.json()
        if not data.get("ok", False):
            raise RuntimeError("Telegram getUpdates returned ok=false")

        result = data.get("result", [])
        if not isinstance(result, list):
            raise RuntimeError("Telegram getUpdates returned a non-list result")
        return result

    def send_message(self, chat_id: str, text: str) -> None:
        if not settings.telegram_bot_token:
            logger.warning("Telegram token is empty; skip sending reply.")
            return

        payload = {"chat_id": chat_id, "text": text}
        response = requests.post(
            f"{self._base_url}/sendMessage",
            json=payload,
            timeout=20,
        )
        response.raise_for_status()


def process_telegram_update(
    update: Dict[str, Any],
    service: ChatService,
    bot_client: TelegramBotClient,
) -> bool:
    message = TelegramParser.parse(update)
    if message is None:
        return False

    response = service.handle_message(message)
    bot_client.send_message(chat_id=message.chat_id, text=response.reply)
    return True


class TelegramPollingWorker:
    def __init__(self, service: ChatService, bot_client: TelegramBotClient) -> None:
        self._service = service
        self._bot_client = bot_client
        self._next_offset: Optional[int] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if not settings.telegram_polling_enabled:
            logger.info("Telegram polling is disabled.")
            return

        if not settings.telegram_bot_token:
            logger.info("Telegram polling is skipped because token is empty.")
            return

        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self.run,
            name="telegram-polling-worker",
        )
        self._thread.start()
        logger.info("Telegram polling worker started.")

    def stop(self) -> None:
        thread = self._thread
        if thread is None:
            return

        self._stop_event.set()
        thread.join(
            timeout=min(
                settings.telegram_polling_timeout_seconds + POLLING_TIMEOUT_BUFFER_SECONDS,
                MAX_TELEGRAM_JOIN_TIMEOUT_SECONDS,
            )
        )
        self._thread = None
        logger.info("Telegram polling worker stopped.")

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                updates = self._bot_client.get_updates(offset=self._next_offset)
                self.process_updates(updates)
            except requests.RequestException as exc:
                logger.exception("Telegram polling request failed: %s", exc)
                self._stop_event.wait(settings.telegram_polling_retry_delay_seconds)
            except Exception as exc:
                logger.exception("Telegram polling worker failed: %s", exc)
                self._stop_event.wait(settings.telegram_polling_retry_delay_seconds)

    def process_updates(self, updates: List[Dict[str, Any]]) -> None:
        for update in updates:
            update_id = update.get("update_id")
            try:
                process_telegram_update(update, service=self._service, bot_client=self._bot_client)
            except Exception as exc:
                logger.exception(
                    "Failed to process Telegram update %s: %s",
                    update_id,
                    exc,
                )
            finally:
                # Advance offset even after a failed update so one bad payload
                # does not block all later messages in the queue.
                if isinstance(update_id, int):
                    self._next_offset = update_id + 1

    @property
    def next_offset(self) -> Optional[int]:
        return self._next_offset
