from unittest.mock import patch, MagicMock
from tests.conftest import AUTH_HEADERS


# ── Authentication tests ──────────────────────────────────────────────────────


def test_cities_requires_api_key(client):
    """
    Requests without X-API-Key must be rejected with 401.
    Verifies the auth middleware is active on protected endpoints.
    """
    response = client.get("/api/v1/cities")
    assert response.status_code == 401


def test_cities_rejects_invalid_api_key(client):
    """
    A wrong key must return 403 — distinguishing 'missing key'
    from 'wrong key' gives consumers a clearer error signal.
    """
    response = client.get("/api/v1/cities", headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 403


# ── Cities endpoint ───────────────────────────────────────────────────────────


def test_list_cities_returns_200(client):
    response = client.get("/api/v1/cities", headers=AUTH_HEADERS)
    assert response.status_code == 200


def test_list_cities_returns_list(client):
    response = client.get("/api/v1/cities", headers=AUTH_HEADERS)
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_list_cities_response_shape(client):
    """
    Each city object must contain all fields defined in CityResponse.
    If a field is accidentally removed from the schema, this catches it.
    """
    response = client.get("/api/v1/cities", headers=AUTH_HEADERS)
    city = response.json()[0]
    assert "id" in city
    assert "name" in city
    assert "country" in city
    assert "continent" in city
    assert "latitude" in city
    assert "longitude" in city
    assert "timezone" in city


def test_list_cities_ordered_alphabetically(client):
    """
    Cities must come back in alphabetical order — the service layer
    orders by name. This test pins that contract so a future refactor
    cannot accidentally break ordering.
    """
    response = client.get("/api/v1/cities", headers=AUTH_HEADERS)
    names = [c["name"] for c in response.json()]
    assert names == sorted(names)


# ── Latest reading for one city ───────────────────────────────────────────────


def test_latest_paris_returns_200(client):
    response = client.get("/api/v1/weather/Paris/latest", headers=AUTH_HEADERS)
    assert response.status_code == 200


def test_latest_paris_response_shape(client):
    """
    Verifies the nested city object is present in the response.
    This was the source of the first 500 error — pinning it here
    prevents regression.
    """
    response = client.get("/api/v1/weather/Paris/latest", headers=AUTH_HEADERS)
    data = response.json()
    assert "temperature" in data
    assert "humidity" in data
    assert "description" in data
    assert "recorded_at" in data
    assert "city" in data
    assert data["city"]["name"] == "Paris"


def test_latest_paris_temperature_is_realistic(client):
    """
    Temperature must be a number within a physically plausible range.
    Catches serialisation bugs where a field is returned as a string
    or as None.
    """
    response = client.get("/api/v1/weather/Paris/latest", headers=AUTH_HEADERS)
    temp = response.json()["temperature"]
    assert isinstance(temp, (int, float))
    assert -80 <= temp <= 60


def test_latest_unknown_city_returns_404(client):
    """
    Requesting a city not in the database must return 404.
    The response contains a detail field explaining the error.
    """
    response = client.get("/api/v1/weather/Atlantis/latest", headers=AUTH_HEADERS)
    assert response.status_code == 404
    assert "detail" in response.json()


def test_latest_case_insensitive(client):
    """
    'paris', 'Paris' and 'PARIS' must all resolve to the same city.
    The service layer uses func.lower() on both sides — this test
    verifies that logic works end to end.
    """
    response_lower = client.get("/api/v1/weather/paris/latest", headers=AUTH_HEADERS)
    response_upper = client.get("/api/v1/weather/PARIS/latest", headers=AUTH_HEADERS)
    assert response_lower.status_code == 200
    assert response_upper.status_code == 200
    assert response_lower.json()["city"]["name"] == "Paris"
    assert response_upper.json()["city"]["name"] == "Paris"


# ── Latest readings for all cities ────────────────────────────────────────────


def test_latest_all_returns_200(client):
    response = client.get("/api/v1/weather/latest", headers=AUTH_HEADERS)
    assert response.status_code == 200


def test_latest_all_returns_list(client):
    response = client.get("/api/v1/weather/latest", headers=AUTH_HEADERS)
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_latest_all_filters_by_continent(client):
    """
    continent=Africa must return only African cities.
    Verifies the join filter in get_latest_readings_all_cities works
    correctly and that no non-African city leaks into the response.
    """
    response = client.get(
        "/api/v1/weather/latest?continent=Africa", headers=AUTH_HEADERS
    )
    assert response.status_code == 200
    data = response.json()
    for reading in data:
        assert reading["city"]["continent"] == "Africa"


def test_latest_all_continent_case_insensitive(client):
    """
    continent filter must be case-insensitive, same convention as
    city name lookups elsewhere in the API.
    """
    response_lower = client.get(
        "/api/v1/weather/latest?continent=africa", headers=AUTH_HEADERS
    )
    response_mixed = client.get(
        "/api/v1/weather/latest?continent=AfRiCa", headers=AUTH_HEADERS
    )
    assert response_lower.status_code == 200
    assert response_mixed.status_code == 200
    assert len(response_lower.json()) == len(response_mixed.json())


def test_latest_all_unknown_continent_returns_empty_list(client):
    """
    A continent with no matching cities returns an empty list,
    not an error — this is correct REST behaviour for a filter
    that legitimately matches nothing.
    """
    response = client.get(
        "/api/v1/weather/latest?continent=Antarctica", headers=AUTH_HEADERS
    )
    assert response.status_code == 200
    assert response.json() == []


# ── History endpoint ──────────────────────────────────────────────────────────


def test_history_paris_returns_200(client):
    response = client.get("/api/v1/weather/Paris/history", headers=AUTH_HEADERS)
    assert response.status_code == 200


def test_history_response_shape(client):
    """
    Paginated responses must include data, total_count, page,
    limit and total_pages — consumers need all five to implement
    pagination on their side.
    """
    response = client.get("/api/v1/weather/Paris/history", headers=AUTH_HEADERS)
    data = response.json()
    assert "data" in data
    assert "total_count" in data
    assert "page" in data
    assert "limit" in data
    assert "total_pages" in data


def test_history_default_page_is_1(client):
    response = client.get("/api/v1/weather/Paris/history", headers=AUTH_HEADERS)
    assert response.json()["page"] == 1


def test_history_default_limit_is_20(client):
    response = client.get("/api/v1/weather/Paris/history", headers=AUTH_HEADERS)
    assert response.json()["limit"] == 20


def test_history_invalid_page_returns_422(client):
    """
    page=0 violates the ge=1 constraint defined on the query parameter.
    FastAPI validates this automatically and returns 422 — no manual
    validation code needed and this test confirms it works.
    """
    response = client.get("/api/v1/weather/Paris/history?page=0", headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_history_limit_above_100_returns_422(client):
    """limit is capped at 100 — requesting 101 must be rejected."""
    response = client.get(
        "/api/v1/weather/Paris/history?limit=101", headers=AUTH_HEADERS
    )
    assert response.status_code == 422


# ── Stats endpoint ────────────────────────────────────────────────────────────


def test_stats_paris_returns_200(client):
    response = client.get("/api/v1/weather/Paris/stats", headers=AUTH_HEADERS)
    assert response.status_code == 200


def test_stats_response_shape(client):
    """
    Stats response must contain aggregated fields and the nested
    city object. All numeric fields must be present.
    """
    response = client.get("/api/v1/weather/Paris/stats", headers=AUTH_HEADERS)
    data = response.json()
    assert "city" in data
    assert "days" in data
    assert "avg_temperature" in data
    assert "min_temperature" in data
    assert "max_temperature" in data
    assert "avg_humidity" in data
    assert "total_readings" in data


def test_stats_days_parameter(client):
    """days=7 must be reflected in the response."""
    response = client.get("/api/v1/weather/Paris/stats?days=7", headers=AUTH_HEADERS)
    assert response.json()["days"] == 7


def test_stats_days_above_30_returns_422(client):
    """days is capped at 30 — prevents expensive queries over large ranges."""
    response = client.get("/api/v1/weather/Paris/stats?days=31", headers=AUTH_HEADERS)
    assert response.status_code == 422


# ── Seeder unit tests with mocking ────────────────────────────────────────────


class TestSeederWithMocking:
    """
    Unit tests for the seeder's OpenWeatherMap integration.

    These tests use unittest.mock.patch to replace the real HTTP call
    with a controlled fake response. This isolates the seeder logic
    from the network entirely — tests run without internet access,
    without an API key, and without consuming API quota.

    This is the correct way to unit test any function that calls
    an external service. The alternative — making real API calls in
    tests — creates flaky tests that fail when the network is slow,
    the API is down, or the rate limit is hit.
    """

    def test_fetch_current_weather_success(self):
        """
        When OpenWeatherMap returns a valid response, fetch_current_weather
        should return the parsed JSON without raising any exception.
        """
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "main": {
                "temp": 26.1,
                "feels_like": 25.8,
                "humidity": 76,
                "pressure": 1015,
            },
            "wind": {"speed": 3.6, "deg": 247},
            "weather": [{"description": "light rain"}],
            "clouds": {"all": 100},
            "visibility": 10000,
        }
        mock_response.raise_for_status.return_value = None

        # patch() temporarily replaces requests.get inside the seed module
        # with our mock. When the seeder calls requests.get(), it gets
        # our fake response instead of making a real HTTP request.
        # The original requests.get is restored after the 'with' block exits.
        with patch(
            "app.seed.seed.requests.get", return_value=mock_response
        ) as mock_get:
            from app.seed.seed import fetch_current_weather

            result = fetch_current_weather(48.8566, 2.3522)

            # Verify the function called requests.get with the right arguments
            mock_get.assert_called_once()
            call_kwargs = mock_get.call_args.kwargs
            assert call_kwargs["params"]["lat"] == 48.8566
            assert call_kwargs["params"]["lon"] == 2.3522
            assert call_kwargs["params"]["units"] == "metric"

            # Verify the result is the parsed JSON
            assert result is not None
            assert result["main"]["temp"] == 26.1

    def test_fetch_current_weather_api_failure_returns_none(self):
        """
        When the API call fails (network error, timeout, rate limit),
        fetch_current_weather must return None instead of crashing.

        The seeder handles None gracefully by falling back to generated
        data — this test verifies that contract holds.
        """
        import requests as req

        with patch(
            "app.seed.seed.requests.get",
            side_effect=req.RequestException("Connection timeout"),
        ):
            from app.seed.seed import fetch_current_weather

            result = fetch_current_weather(48.8566, 2.3522)
            assert result is None

    def test_parse_current_weather_extracts_correct_fields(self):
        """
        parse_current_weather must map OpenWeatherMap's nested JSON
        structure to a WeatherReading model correctly.

        This test verifies the field mapping without touching the database
        or the network — pure function logic only.
        """
        from app.seed.seed import parse_current_weather

        raw_api_response = {
            "main": {
                "temp": 33.4,
                "feels_like": 36.0,
                "humidity": 45,
                "pressure": 1008,
            },
            "wind": {"speed": 5.2, "deg": 120},
            "weather": [{"description": "clear sky"}],
            "clouds": {"all": 0},
            "visibility": 10000,
        }

        reading = parse_current_weather(raw_api_response, city_id=1)

        assert reading.temperature == 33.4
        assert reading.feels_like == 36.0
        assert reading.humidity == 45
        assert reading.pressure == 1008
        assert reading.wind_speed == 5.2
        assert reading.wind_direction == 120
        assert reading.description == "clear sky"
        assert reading.cloudiness == 0
        assert reading.city_id == 1

    def test_generate_historical_reading_temperature_variance(self):
        """
        Generated historical readings must vary within a reasonable range
        around the anchor temperature. A reading 50 degrees away from
        the current temperature would be physically implausible.

        This test pins the variance contract — if someone changes the
        random range in generate_historical_reading, this catches it.
        """
        from app.seed.seed import generate_historical_reading
        from datetime import datetime

        anchor_temp = 26.0
        recorded_at = datetime(2026, 6, 18, 14, 0, 0)

        # Generate 20 readings and verify none deviate wildly
        readings = [
            generate_historical_reading(
                city_id=1,
                current_temp=anchor_temp,
                recorded_at=recorded_at,
            )
            for _ in range(20)
        ]

        for reading in readings:
            assert reading.city_id == 1
            assert isinstance(reading.temperature, float)
            # Variance is +/- 6 degrees — allow generous margin
            assert anchor_temp - 10 <= reading.temperature <= anchor_temp + 10
            assert 0 <= reading.humidity <= 100
            assert 0 <= reading.cloudiness <= 100
            assert reading.wind_speed >= 0
