"""
Tests for GET /api/v1/weather/compare

The compare endpoint returns side-by-side weather statistics for two
cities over N days, with deltas computed as city_b minus city_a.

All tests run against SQLite with seeded fixtures — no network, no
PostgreSQL, no OpenWeatherMap. The fixture cities are Paris and Tokyo,
seeded in conftest.py with known temperatures so delta assertions are
deterministic.

What we're proving:
- 401 when API key is missing
- 403 when API key is wrong
- 200 with valid city_a, city_b and days
- Response shape: days, city_a, city_b, temperature_delta, humidity_delta, wind_speed_delta
- city_a and city_b objects contain expected city fields
- temperature_delta equals city_b avg minus city_a avg
- Same city in both parameters returns 422
- Unknown city_a returns 404
- Unknown city_b returns 404
- days=0 returns 422 (below minimum)
- days=31 returns 422 (above maximum)
- days defaults to 7 when not supplied
"""

from tests.conftest import AUTH_HEADERS


# -- Authentication ----------------------------------------------------------


def test_compare_requires_api_key(client):
    """
    Missing API key must return 401.
    The compare endpoint is protected by the same auth middleware
    as all other weather endpoints.
    """
    response = client.get("/api/v1/weather/compare?city_a=Paris&city_b=Tokyo")
    assert response.status_code == 401


def test_compare_rejects_wrong_api_key(client):
    """
    A wrong key must return 403, not 401 — distinguishing missing
    from wrong gives consumers a clearer error signal.
    """
    response = client.get(
        "/api/v1/weather/compare?city_a=Paris&city_b=Tokyo",
        headers={"X-API-Key": "wrong-key"},
    )
    assert response.status_code == 403


# -- Happy path --------------------------------------------------------------


def test_compare_returns_200(client):
    """
    Valid city_a, city_b and days must return 200.
    """
    response = client.get(
        "/api/v1/weather/compare?city_a=Paris&city_b=Tokyo&days=7",
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200


def test_compare_response_shape(client):
    """
    Response must contain days, city_a, city_b and all three delta fields.
    If a field is accidentally removed from WeatherComparisonResponse,
    this catches it before it reaches consumers.
    """
    response = client.get(
        "/api/v1/weather/compare?city_a=Paris&city_b=Tokyo&days=7",
        headers=AUTH_HEADERS,
    )
    data = response.json()
    assert "days" in data
    assert "city_a" in data
    assert "city_b" in data
    assert "temperature_delta" in data
    assert "humidity_delta" in data
    assert "wind_speed_delta" in data


def test_compare_city_objects_shape(client):
    """
    Each city object inside the comparison must contain the full
    stats payload: city metadata plus all aggregated metrics.
    """
    response = client.get(
        "/api/v1/weather/compare?city_a=Paris&city_b=Tokyo&days=7",
        headers=AUTH_HEADERS,
    )
    data = response.json()
    for key in ("city_a", "city_b"):
        city_stats = data[key]
        assert "city" in city_stats
        assert "avg_temperature" in city_stats
        assert "min_temperature" in city_stats
        assert "max_temperature" in city_stats
        assert "avg_humidity" in city_stats
        assert "min_humidity" in city_stats
        assert "max_humidity" in city_stats
        assert "avg_wind_speed" in city_stats
        assert "total_readings" in city_stats


def test_compare_city_metadata(client):
    """
    city_a.city.name must be Paris and city_b.city.name must be Tokyo.
    Verifies the service is not swapping city order.
    """
    response = client.get(
        "/api/v1/weather/compare?city_a=Paris&city_b=Tokyo&days=7",
        headers=AUTH_HEADERS,
    )
    data = response.json()
    assert data["city_a"]["city"]["name"] == "Paris"
    assert data["city_b"]["city"]["name"] == "Tokyo"


def test_compare_days_reflected_in_response(client):
    """
    The days field in the response must match the requested days parameter.
    """
    response = client.get(
        "/api/v1/weather/compare?city_a=Paris&city_b=Tokyo&days=14",
        headers=AUTH_HEADERS,
    )
    assert response.json()["days"] == 14


def test_compare_temperature_delta_is_city_b_minus_city_a(client):
    """
    temperature_delta must equal avg_temperature(city_b) minus
    avg_temperature(city_a), rounded to 2 decimal places.
    This pins the delta direction contract — a positive delta means
    city_b is warmer, a negative delta means city_a is warmer.
    """
    response = client.get(
        "/api/v1/weather/compare?city_a=Paris&city_b=Tokyo&days=7",
        headers=AUTH_HEADERS,
    )
    data = response.json()
    expected_delta = round(
        data["city_b"]["avg_temperature"] - data["city_a"]["avg_temperature"], 2
    )
    assert data["temperature_delta"] == expected_delta


def test_compare_humidity_delta_is_city_b_minus_city_a(client):
    """
    humidity_delta must equal avg_humidity(city_b) minus avg_humidity(city_a).
    """
    response = client.get(
        "/api/v1/weather/compare?city_a=Paris&city_b=Tokyo&days=7",
        headers=AUTH_HEADERS,
    )
    data = response.json()
    expected_delta = round(
        data["city_b"]["avg_humidity"] - data["city_a"]["avg_humidity"], 2
    )
    assert data["humidity_delta"] == expected_delta


def test_compare_wind_speed_delta_is_city_b_minus_city_a(client):
    """
    wind_speed_delta must equal avg_wind_speed(city_b) minus avg_wind_speed(city_a).
    """
    response = client.get(
        "/api/v1/weather/compare?city_a=Paris&city_b=Tokyo&days=7",
        headers=AUTH_HEADERS,
    )
    data = response.json()
    expected_delta = round(
        data["city_b"]["avg_wind_speed"] - data["city_a"]["avg_wind_speed"], 2
    )
    assert data["wind_speed_delta"] == expected_delta


def test_compare_case_insensitive(client):
    """
    City names must be resolved case-insensitively — paris and PARIS
    must resolve to the same city. This mirrors the existing behaviour
    on all other city endpoints.
    """
    response = client.get(
        "/api/v1/weather/compare?city_a=paris&city_b=TOKYO&days=7",
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["city_a"]["city"]["name"] == "Paris"
    assert data["city_b"]["city"]["name"] == "Tokyo"


def test_compare_defaults_to_7_days(client):
    """
    When days is not supplied, the endpoint must default to 7.
    """
    response = client.get(
        "/api/v1/weather/compare?city_a=Paris&city_b=Tokyo",
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["days"] == 7


# -- Validation errors -------------------------------------------------------


def test_compare_same_city_returns_422(client):
    """
    Comparing a city to itself must return 422.
    The delta would always be zero — a meaningless response that signals
    a consumer mistake rather than a valid use case.
    """
    response = client.get(
        "/api/v1/weather/compare?city_a=Paris&city_b=Paris&days=7",
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 422


def test_compare_unknown_city_a_returns_404(client):
    """
    An unrecognised city_a must return 404 with a helpful message.
    """
    response = client.get(
        "/api/v1/weather/compare?city_a=Atlantis&city_b=Tokyo&days=7",
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 404


def test_compare_unknown_city_b_returns_404(client):
    """
    An unrecognised city_b must return 404 with a helpful message.
    """
    response = client.get(
        "/api/v1/weather/compare?city_a=Paris&city_b=Atlantis&days=7",
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 404


def test_compare_days_below_minimum_returns_422(client):
    """
    days=0 must return 422 — FastAPI validates ge=1 automatically.
    """
    response = client.get(
        "/api/v1/weather/compare?city_a=Paris&city_b=Tokyo&days=0",
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 422


def test_compare_days_above_maximum_returns_422(client):
    """
    days=31 must return 422 — FastAPI validates le=30 automatically.
    """
    response = client.get(
        "/api/v1/weather/compare?city_a=Paris&city_b=Tokyo&days=31",
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 422
