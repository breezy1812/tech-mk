import logging
import threading
from typing import Any, Dict, List, Optional

import requests

from app.config import settings
from app.connectors.telegram_handler import TelegramParser
from app.domain.schemas.rag import RAGQueryResponse, RAGStatusResponse
from app.ollama_client import OllamaUnavailableError
from app.service import ChatService
from app.services.indexing_service import IndexingService
from app.services.rag_service import RAGBackendError, RAGService

logger = logging.getLogger(__name__)
# Keep the HTTP client timeout slightly above Telegram long-polling timeout
# so the local request doesn't expire before Telegram responds.
POLLING_TIMEOUT_BUFFER_SECONDS = 10
MAX_TELEGRAM_HTTP_TIMEOUT_SECONDS = 60
MAX_TELEGRAM_JOIN_TIMEOUT_SECONDS = 60
OLLAMA_UNAVAILABLE_REPLY = "抱歉，目前知識服務暫時不可用，請稍後再試。"
ASKDOC_USAGE_REPLY = "用法: /askdoc <問題>"
REINDEX_FORBIDDEN_REPLY = "只有管理員可以執行 /reindex。"
REINDEX_DISABLED_REPLY = "目前未開放從 Telegram 執行重建索引。"
SYNC_FORBIDDEN_REPLY = "只有管理員可以執行 /sync。"
SYNC_DISABLED_REPLY = "目前未開放從 Telegram 執行增量同步。"
RAG_BACKEND_ERROR_REPLY = "抱歉，目前文件查詢服務暫時不可用，請稍後再試。"


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
    indexing_service: Optional[IndexingService] = None,
    rag_service: Optional[RAGService] = None,
) -> bool:
    message = TelegramParser.parse(update)
    if message is None:
        return False

    text = message.text.strip()

    try:
        if text.startswith("/askdoc"):
            reply = _handle_askdoc(text=text, rag_service=rag_service)
        elif text == "/ragstatus":
            reply = _handle_ragstatus(indexing_service=indexing_service)
        elif text == "/sync":
            reply = _handle_sync(message_user_id=message.user_id, indexing_service=indexing_service)
        elif text == "/reindex":
            reply = _handle_reindex(message_user_id=message.user_id, indexing_service=indexing_service)
        else:
            response = service.handle_message(message)
            reply = response.reply
    except OllamaUnavailableError as exc:
        logger.warning("Ollama unavailable while handling Telegram update: %s", exc)
        reply = OLLAMA_UNAVAILABLE_REPLY
    except RAGBackendError as exc:
        logger.warning("RAG backend unavailable while handling Telegram update: %s", exc)
        reply = RAG_BACKEND_ERROR_REPLY

    bot_client.send_message(chat_id=message.chat_id, text=reply)
    return True


def _handle_askdoc(text: str, rag_service: Optional[RAGService]) -> str:
    if rag_service is None:
        raise RAGBackendError("RAG service is not configured")

    question = text[len("/askdoc") :].strip()
    if not question:
        return ASKDOC_USAGE_REPLY

    result = rag_service.query(question=question, top_k=settings.rag_top_k, debug=False)
    return _format_askdoc_reply(result)


def _handle_ragstatus(indexing_service: Optional[IndexingService]) -> str:
    if indexing_service is None:
        raise RAGBackendError("Indexing service is not configured")

    status = indexing_service.status()
    return _format_ragstatus_reply(status)


def _handle_reindex(message_user_id: str, indexing_service: Optional[IndexingService]) -> str:
    if not settings.rag_allow_reindex:
        return REINDEX_DISABLED_REPLY
    if message_user_id not in settings.telegram_admin_user_id_set:
        return REINDEX_FORBIDDEN_REPLY
    if indexing_service is None:
        raise RAGBackendError("Indexing service is not configured")

    report = indexing_service.reindex()
    return (
        f"索引重建完成。檔案數: {report.files_processed}，"
        f"chunks: {report.chunks_indexed}，"
        f"失敗檔案: {len(report.failed_files)}"
    )


def _handle_sync(message_user_id: str, indexing_service: Optional[IndexingService]) -> str:
    if not settings.rag_allow_reindex:
        return SYNC_DISABLED_REPLY
    if message_user_id not in settings.telegram_admin_user_id_set:
        return SYNC_FORBIDDEN_REPLY
    if indexing_service is None:
        raise RAGBackendError("Indexing service is not configured")

    report = indexing_service.sync_index()
    return (
        f"增量同步完成。更新檔案: {report.files_indexed}，"
        f"未變更檔案: {report.files_unchanged}，"
        f"刪除檔案: {report.files_deleted}，"
        f"失敗檔案: {len(report.failed_files)}"
    )


def _format_askdoc_reply(result: RAGQueryResponse) -> str:
    if not result.sources:
        return result.answer

    file_names = ", ".join(dict.fromkeys(source.file for source in result.sources))
    return f"{result.answer}\n\n來源: {file_names}"


def _format_ragstatus_reply(status: RAGStatusResponse) -> str:
    last_indexed = status.last_indexed_at.isoformat() if status.last_indexed_at else "尚未建立索引"
    return (
        f"Collection: {status.collection_name}\n"
        f"文件數: {status.indexed_files}\n"
        f"Chunks: {status.indexed_chunks}\n"
        f"最後索引時間: {last_indexed}"
    )


class TelegramPollingWorker:
    def __init__(
        self,
        service: ChatService,
        bot_client: TelegramBotClient,
        indexing_service: Optional[IndexingService] = None,
        rag_service: Optional[RAGService] = None,
    ) -> None:
        self._service = service
        self._bot_client = bot_client
        self._indexing_service = indexing_service
        self._rag_service = rag_service
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
                process_telegram_update(
                    update,
                    service=self._service,
                    bot_client=self._bot_client,
                    indexing_service=self._indexing_service,
                    rag_service=self._rag_service,
                )
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
