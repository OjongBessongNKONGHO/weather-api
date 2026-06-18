from tests.conftest import AUTH_HEADERS


def test_health_check_returns_200(client):
    """
    Health endpoint must return 200 with no authentication.
    Infrastructure tools and load balancers call this without credentials.
    """
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_health_check_response_shape(client):
    """
    Verifies the response contains all required fields with correct types.
    A monitoring tool that parses this response needs a stable contract.
    """
    response = client.get("/api/v1/health")
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] in ("connected", "unavailable")
    assert data["version"] == "1.0.0"
    assert "environment" in data


def test_health_check_requires_no_api_key(client):
    """
    Confirms health is accessible without X-API-Key.
    If this fails, infrastructure tooling breaks.
    """
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_unknown_endpoint_returns_404(client):
    """
    Any path not defined in the routers returns a clean JSON 404
    with a pointer to /docs — not a plain text error.
    """
    response = client.get("/api/v1/nonexistent")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "docs" in data
