from fastapi.testclient import TestClient

from app.main import app


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
