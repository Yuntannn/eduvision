from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_docs_are_served(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_unknown_route_uses_standard_error_format(client: TestClient) -> None:
    response = client.get("/nope")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
