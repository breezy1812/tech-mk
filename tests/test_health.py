from fastapi.testclient import TestClient

from app.main import app
from app.models import ChatResponse
from app.telegram_polling import TelegramPollingWorker, process_telegram_update


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_config_check_shows_telegram_polling_flag() -> None:
    response = client.get("/config/check")
    assert response.status_code == 200
    data = response.json()
    assert "telegram_polling_enabled" in data


def test_process_telegram_update_sends_reply() -> None:
    captured = {}

    class FakeService:
        def handle_message(self, message):  # type: ignore[no-untyped-def]
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


def test_polling_worker_advances_offset_for_each_update() -> None:
    class FakeService:
        def handle_message(self, message):  # type: ignore[no-untyped-def]
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
                    "text": "one",
                    "from": {"id": 1},
                    "chat": {"id": 11},
                },
            },
            {
                "update_id": 11,
                "message": {
                    "text": "two",
                    "from": {"id": 2},
                    "chat": {"id": 22},
                },
            },
        ]
    )

    assert worker._next_offset == 12
    assert bot_client.sent_messages == [("11", "echo:one"), ("22", "echo:two")]
