"""
Rate limiting tests.

Verifies the 60/minute limit enforced by slowapi on every weather
endpoint: the first 60 requests within the window succeed, and the
61st is rejected with 429.

limiter.reset() is called before and after hammering the endpoint.
Without this, the test would be order-dependent: the client fixture
is session-scoped and shared with every other test in this suite,
and slowapi keys its limit by client IP - which TestClient always
reports as the same address. Any request another test already made
to the same endpoint in this session would eat into this test's
budget, and this test blowing the limit would in turn cause 429s in
whichever test happens to run after it. Resetting before isolates
this test from what ran earlier; resetting after protects whatever
runs next.
"""

from tests.conftest import AUTH_HEADERS
from app.limiter import limiter


class TestRateLimit:

    def test_first_60_requests_succeed_then_61st_is_rate_limited(self, client):
        """The 60/minute limit must allow exactly 60 requests through
        and reject the 61st with 429."""
        limiter.reset()

        for i in range(60):
            response = client.get("/api/v1/cities", headers=AUTH_HEADERS)
            assert (
                response.status_code == 200
            ), f"request {i + 1} of 60 should succeed, got {response.status_code}"

        response = client.get("/api/v1/cities", headers=AUTH_HEADERS)
        assert response.status_code == 429

        limiter.reset()

    def test_429_response_reports_the_rate_limit(self, client):
        """The 429 body must actually say what the limit is - a bare
        429 with no explanation isn't useful to an API consumer trying
        to figure out how hard they can retry."""
        limiter.reset()

        for _ in range(60):
            client.get("/api/v1/cities", headers=AUTH_HEADERS)

        response = client.get("/api/v1/cities", headers=AUTH_HEADERS)

        assert response.status_code == 429
        body = response.json()
        assert "60" in body["error"]

        limiter.reset()

    def test_rate_limit_is_scoped_per_endpoint_not_global(self, client):
        """Exhausting the limit on one endpoint must not block a
        different endpoint - each route has its own @limiter.limit
        decorator, so each should track its own independent budget."""
        limiter.reset()

        for _ in range(60):
            client.get("/api/v1/cities", headers=AUTH_HEADERS)
        blocked_response = client.get("/api/v1/cities", headers=AUTH_HEADERS)
        assert blocked_response.status_code == 429

        other_endpoint_response = client.get(
            "/api/v1/weather/latest", headers=AUTH_HEADERS
        )
        assert other_endpoint_response.status_code == 200

        limiter.reset()
