from app.models import ChatResponse, NormalizedMessage
from app.ollama_client import OllamaUnavailableError
from app.telegram_polling import OLLAMA_UNAVAILABLE_REPLY, TelegramPollingWorker, process_telegram_update


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
