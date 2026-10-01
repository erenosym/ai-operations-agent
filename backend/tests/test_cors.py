from fastapi.testclient import TestClient
from app.main import app


def test_frontend_preflight_is_narrow():
    client = TestClient(app)
    headers = {"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
               "Access-Control-Request-Headers": "content-type"}
    response = client.options("/agent/run", headers=headers)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    headers["Origin"] = "https://untrusted.example"
    response = client.options("/agent/run", headers=headers)
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
