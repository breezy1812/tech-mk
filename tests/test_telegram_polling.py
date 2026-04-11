from datetime import datetime, timezone

from app.config import settings
from app.models import ChatResponse, NormalizedMessage
from app.domain.schemas.rag import ChunkSource, IndexingReport, RAGQueryResponse, RAGStatusResponse
from app.ollama_client import OllamaUnavailableError
from app.telegram_polling import (
    ASKDOC_USAGE_REPLY,
    OLLAMA_UNAVAILABLE_REPLY,
    REINDEX_DISABLED_REPLY,
    REINDEX_FORBIDDEN_REPLY,
    TelegramPollingWorker,
    process_telegram_update,
)


def test_process_telegram_update_sends_reply() -> None:
    captured = {}

    class FakeService:
        def handle_message(self, message: NormalizedMessage) -> ChatResponse:
            captured["message"] = message
            return ChatResponse(reply="pong", model="test-model")

    class FakeBotClient:
        def send_message(self, chat_id: str, text: str) -> None:
            captured["chat_id"] = chat_id
            captured["text"] = text

    processed = process_telegram_update(
        {
            "update_id": 1000,
            "message": {
                "message_id": 1,
                "text": "ping",
                "from": {"id": 123},
                "chat": {"id": 456},
            },
        },
        service=FakeService(),
        bot_client=FakeBotClient(),
    )

    assert processed is True
    assert captured["message"].text == "ping"
    assert captured["chat_id"] == "456"
    assert captured["text"] == "pong"


def test_process_telegram_update_handles_askdoc_command() -> None:
    captured = {}

    class FakeService:
        def handle_message(self, message: NormalizedMessage) -> ChatResponse:
            raise AssertionError("chat service should not be called for /askdoc")

    class FakeRAGService:
        def query(self, question: str, top_k: int | None = None, debug: bool | None = None) -> RAGQueryResponse:
            captured["question"] = question
            return RAGQueryResponse(
                answer="RAG answer",
                sources=[ChunkSource(file="guide.md", chunk=0, relative_path="guide.md")],
            )

    class FakeBotClient:
        def send_message(self, chat_id: str, text: str) -> None:
            captured["chat_id"] = chat_id
            captured["text"] = text

    processed = process_telegram_update(
        {
            "update_id": 1002,
            "message": {
                "message_id": 3,
                "text": "/askdoc What is RAG?",
                "from": {"id": 123},
                "chat": {"id": 456},
            },
        },
        service=FakeService(),
        bot_client=FakeBotClient(),
        rag_service=FakeRAGService(),
    )

    assert processed is True
    assert captured["question"] == "What is RAG?"
    assert "RAG answer" in captured["text"]
    assert "guide.md" in captured["text"]


def test_process_telegram_update_handles_askdoc_usage_error() -> None:
    captured = {}

    class FakeBotClient:
        def send_message(self, chat_id: str, text: str) -> None:
            captured["text"] = text

    processed = process_telegram_update(
        {
            "update_id": 1003,
            "message": {
                "message_id": 4,
                "text": "/askdoc",
                "from": {"id": 123},
                "chat": {"id": 456},
            },
        },
        service=object(),
        bot_client=FakeBotClient(),
        rag_service=object(),
    )

    assert processed is True
    assert captured["text"] == ASKDOC_USAGE_REPLY


def test_process_telegram_update_sends_fallback_when_ollama_is_unavailable() -> None:
    captured = {}

    class FakeService:
        def handle_message(self, message: NormalizedMessage) -> ChatResponse:
            captured["message"] = message
            raise OllamaUnavailableError("connection refused")

    class FakeBotClient:
        def send_message(self, chat_id: str, text: str) -> None:
            captured["chat_id"] = chat_id
            captured["text"] = text

    processed = process_telegram_update(
        {
            "update_id": 1001,
            "message": {
                "message_id": 2,
                "text": "ping",
                "from": {"id": 123},
                "chat": {"id": 456},
            },
        },
        service=FakeService(),
        bot_client=FakeBotClient(),
    )

    assert processed is True
    assert captured["message"].text == "ping"
    assert captured["chat_id"] == "456"
    assert captured["text"] == OLLAMA_UNAVAILABLE_REPLY


def test_process_telegram_update_handles_ragstatus_command() -> None:
    captured = {}

    class FakeService:
        def handle_message(self, message: NormalizedMessage) -> ChatResponse:
            raise AssertionError("chat service should not be called for /ragstatus")

    class FakeIndexingService:
        def status(self) -> RAGStatusResponse:
            return RAGStatusResponse(
                enabled=True,
                collection_name="tech_docs",
                embedding_model="fake-embed",
                docs_root="data/docs",
                chunk_size=800,
                chunk_overlap=120,
                indexed_files=2,
                indexed_chunks=5,
                last_indexed_at=datetime.now(timezone.utc),
                last_report=None,
            )

    class FakeBotClient:
        def send_message(self, chat_id: str, text: str) -> None:
            captured["text"] = text

    processed = process_telegram_update(
        {
            "update_id": 1004,
            "message": {
                "message_id": 5,
                "text": "/ragstatus",
                "from": {"id": 123},
                "chat": {"id": 456},
            },
        },
        service=FakeService(),
        bot_client=FakeBotClient(),
        indexing_service=FakeIndexingService(),
    )

    assert processed is True
    assert "tech_docs" in captured["text"]
    assert "Chunks: 5" in captured["text"]


def test_process_telegram_update_rejects_reindex_for_non_admin() -> None:
    captured = {}
    original_allow_reindex = settings.rag_allow_reindex
    original_admin_users = settings.telegram_admin_user_ids

    class FakeBotClient:
        def send_message(self, chat_id: str, text: str) -> None:
            captured["text"] = text

    try:
        settings.rag_allow_reindex = True
        settings.telegram_admin_user_ids = "999"
        processed = process_telegram_update(
            {
                "update_id": 1005,
                "message": {
                    "message_id": 6,
                    "text": "/reindex",
                    "from": {"id": 123},
                    "chat": {"id": 456},
                },
            },
            service=object(),
            bot_client=FakeBotClient(),
            indexing_service=object(),
        )
    finally:
        settings.rag_allow_reindex = original_allow_reindex
        settings.telegram_admin_user_ids = original_admin_users

    assert processed is True
    assert captured["text"] == REINDEX_FORBIDDEN_REPLY


def test_process_telegram_update_reindex_disabled() -> None:
    captured = {}
    original_allow_reindex = settings.rag_allow_reindex

    class FakeBotClient:
        def send_message(self, chat_id: str, text: str) -> None:
            captured["text"] = text

    try:
        settings.rag_allow_reindex = False
        processed = process_telegram_update(
            {
                "update_id": 1006,
                "message": {
                    "message_id": 7,
                    "text": "/reindex",
                    "from": {"id": 123},
                    "chat": {"id": 456},
                },
            },
            service=object(),
            bot_client=FakeBotClient(),
            indexing_service=object(),
        )
    finally:
        settings.rag_allow_reindex = original_allow_reindex

    assert processed is True
    assert captured["text"] == REINDEX_DISABLED_REPLY


def test_process_telegram_update_runs_reindex_for_admin() -> None:
    captured = {}
    original_allow_reindex = settings.rag_allow_reindex
    original_admin_users = settings.telegram_admin_user_ids

    class FakeIndexingService:
        def reindex(self) -> IndexingReport:
            return IndexingReport(
                collection_name="tech_docs",
                embedding_model="fake-embed",
                docs_root="data/docs",
                files_processed=2,
                chunks_indexed=4,
                files=[],
                failed_files=[],
                indexed_at=datetime.now(timezone.utc),
            )

    class FakeBotClient:
        def send_message(self, chat_id: str, text: str) -> None:
            captured["text"] = text

    try:
        settings.rag_allow_reindex = True
        settings.telegram_admin_user_ids = "123"
        processed = process_telegram_update(
            {
                "update_id": 1007,
                "message": {
                    "message_id": 8,
                    "text": "/reindex",
                    "from": {"id": 123},
                    "chat": {"id": 456},
                },
            },
            service=object(),
            bot_client=FakeBotClient(),
            indexing_service=FakeIndexingService(),
        )
    finally:
        settings.rag_allow_reindex = original_allow_reindex
        settings.telegram_admin_user_ids = original_admin_users

    assert processed is True
    assert "索引重建完成" in captured["text"]


def test_polling_worker_advances_offset_for_each_update() -> None:
    class FakeService:
        def handle_message(self, message: NormalizedMessage) -> ChatResponse:
            return ChatResponse(reply=f"echo:{message.text}", model="test-model")

    class FakeBotClient:
        def __init__(self) -> None:
            self.sent_messages = []

        def send_message(self, chat_id: str, text: str) -> None:
            self.sent_messages.append((chat_id, text))

    bot_client = FakeBotClient()
    worker = TelegramPollingWorker(service=FakeService(), bot_client=bot_client)
    worker.process_updates(
        [
            {
                "update_id": 10,
                "message": {
                    "message_id": 2,
                    "text": "one",
                    "from": {"id": 1},
                    "chat": {"id": 11},
                },
            },
            {
                "update_id": 11,
                "message": {
                    "message_id": 3,
                    "text": "two",
                    "from": {"id": 2},
                    "chat": {"id": 22},
                },
            },
        ]
    )

    assert worker.next_offset == 12
    assert bot_client.sent_messages == [("11", "echo:one"), ("22", "echo:two")]
