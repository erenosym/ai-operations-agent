from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app import main


def test_health_when_database_is_available(monkeypatch) -> None:
    check_connection = AsyncMock(return_value=None)
    monkeypatch.setattr(main, "check_database_connection", check_connection)

    with TestClient(main.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "ai-operations-agent-api",
        "services": {"database": "ok"},
    }
    check_connection.assert_awaited_once_with()


def test_health_when_database_is_unavailable(monkeypatch) -> None:
    check_connection = AsyncMock(side_effect=OSError("database unavailable"))
    monkeypatch.setattr(main, "check_database_connection", check_connection)

    with TestClient(main.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "service": "ai-operations-agent-api",
        "services": {"database": "unavailable"},
    }


def test_health_does_not_expose_database_details(monkeypatch) -> None:
    sensitive_details = "postgresql+asyncpg://secret-user:secret-password@db/internal"
    check_connection = AsyncMock(side_effect=OSError(sensitive_details))
    monkeypatch.setattr(main, "check_database_connection", check_connection)

    with TestClient(main.app) as client:
        response = client.get("/health")

    response_body = response.text
    assert "secret-user" not in response_body
    assert "secret-password" not in response_body
    assert "postgresql+asyncpg" not in response_body
