import logging
import random
import requests
from datetime import datetime, timedelta, UTC
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.models.weather import City, WeatherReading
from app.config import settings

# This is a standalone CLI script (run via `python -m app.seed.seed`), not
# part of the request-serving app — it runs once, sequentially, so it has
# no need for async I/O. It gets its own small synchronous engine here
# rather than importing from app.database (which is async-only), the same
# reasoning that keeps Alembic's migrations synchronous. psycopg3 speaks
# both sync and async from the same driver, so this reuses the exact same
# DATABASE_URL with no extra configuration needed.
_sync_engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=_sync_engine)
# Configure module-level logger.
# In production, log level and handlers are configured once at application
# startup — every module just gets a logger by name and the root configuration
# controls where logs go (stdout, file, CloudWatch, Datadog, etc.).
logger = logging.getLogger(__name__)

# Fixed seed for reproducible historical data generation.
# Current readings come from the real API — history is generated
# with a fixed seed so it is consistent across runs.
random.seed(42)

CITIES = [
    {
        "name": "Paris",
        "country": "France",
        "continent": "Europe",
        "latitude": 48.8566,
        "longitude": 2.3522,
        "timezone": "Europe/Paris",
    },
    {
        "name": "London",
        "country": "United Kingdom",
        "continent": "Europe",
        "latitude": 51.5074,
        "longitude": -0.1278,
        "timezone": "Europe/London",
    },
    {
        "name": "Berlin",
        "country": "Germany",
        "continent": "Europe",
        "latitude": 52.5200,
        "longitude": 13.4050,
        "timezone": "Europe/Berlin",
    },
    {
        "name": "Amsterdam",
        "country": "Netherlands",
        "continent": "Europe",
        "latitude": 52.3676,
        "longitude": 4.9041,
        "timezone": "Europe/Amsterdam",
    },
    {
        "name": "Madrid",
        "country": "Spain",
        "continent": "Europe",
        "latitude": 40.4168,
        "longitude": -3.7038,
        "timezone": "Europe/Madrid",
    },
    {
        "name": "New York",
        "country": "United States",
        "continent": "North America",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "timezone": "America/New_York",
    },
    {
        "name": "Toronto",
        "country": "Canada",
        "continent": "North America",
        "latitude": 43.6532,
        "longitude": -79.3832,
        "timezone": "America/Toronto",
    },
    {
        "name": "Mexico City",
        "country": "Mexico",
        "continent": "North America",
        "latitude": 19.4326,
        "longitude": -99.1332,
        "timezone": "America/Mexico_City",
    },
    {
        "name": "Sao Paulo",
        "country": "Brazil",
        "continent": "South America",
        "latitude": -23.5505,
        "longitude": -46.6333,
        "timezone": "America/Sao_Paulo",
    },
    {
        "name": "Buenos Aires",
        "country": "Argentina",
        "continent": "South America",
        "latitude": -34.6037,
        "longitude": -58.3816,
        "timezone": "America/Argentina/Buenos_Aires",
    },
    {
        "name": "Douala",
        "country": "Cameroon",
        "continent": "Africa",
        "latitude": 4.0511,
        "longitude": 9.7679,
        "timezone": "Africa/Douala",
    },
    {
        "name": "Lagos",
        "country": "Nigeria",
        "continent": "Africa",
        "latitude": 6.5244,
        "longitude": 3.3792,
        "timezone": "Africa/Lagos",
    },
    {
        "name": "Nairobi",
        "country": "Kenya",
        "continent": "Africa",
        "latitude": -1.2921,
        "longitude": 36.8219,
        "timezone": "Africa/Nairobi",
    },
    {
        "name": "Cairo",
        "country": "Egypt",
        "continent": "Africa",
        "latitude": 30.0444,
        "longitude": 31.2357,
        "timezone": "Africa/Cairo",
    },
    {
        "name": "Johannesburg",
        "country": "South Africa",
        "continent": "Africa",
        "latitude": -26.2041,
        "longitude": 28.0473,
        "timezone": "Africa/Johannesburg",
    },
    {
        "name": "Tokyo",
        "country": "Japan",
        "continent": "Asia",
        "latitude": 35.6762,
        "longitude": 139.6503,
        "timezone": "Asia/Tokyo",
    },
    {
        "name": "Mumbai",
        "country": "India",
        "continent": "Asia",
        "latitude": 19.0760,
        "longitude": 72.8777,
        "timezone": "Asia/Kolkata",
    },
    {
        "name": "Dubai",
        "country": "United Arab Emirates",
        "continent": "Asia",
        "latitude": 25.2048,
        "longitude": 55.2708,
        "timezone": "Asia/Dubai",
    },
    {
        "name": "Singapore",
        "country": "Singapore",
        "continent": "Asia",
        "latitude": 1.3521,
        "longitude": 103.8198,
        "timezone": "Asia/Singapore",
    },
    {
        "name": "Seoul",
        "country": "South Korea",
        "continent": "Asia",
        "latitude": 37.5665,
        "longitude": 126.9780,
        "timezone": "Asia/Seoul",
    },
    {
        "name": "Sydney",
        "country": "Australia",
        "continent": "Oceania",
        "latitude": -33.8688,
        "longitude": 151.2093,
        "timezone": "Australia/Sydney",
    },
]

WEATHER_CONDITIONS = [
    "clear sky",
    "few clouds",
    "scattered clouds",
    "broken clouds",
    "light rain",
    "moderate rain",
    "overcast clouds",
    "light drizzle",
]


def fetch_current_weather(lat: float, lon: float) -> dict | None:
    """
    Fetches real current weather from OpenWeatherMap for a given
    latitude and longitude.

    Returns None on any failure — the seeder falls back to generated
    data for that city rather than crashing. This makes the seeder
    resilient to transient API failures or rate limits.

    Units are metric — temperatures in Celsius, wind speed in m/s.
    """
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": settings.openweather_api_key,
        "units": "metric",
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.warning("API call failed (%s). Using generated data.", e)
        return None


def parse_current_weather(data: dict, city_id: int) -> WeatherReading:
    """
    Maps the OpenWeatherMap API response to a WeatherReading model.

    The API returns nested JSON — main.temp, wind.speed, clouds.all etc.
    We extract only the fields our schema defines and discard the rest.
    """
    return WeatherReading(
        city_id=city_id,
        temperature=round(data["main"]["temp"], 1),
        feels_like=round(data["main"]["feels_like"], 1),
        humidity=data["main"]["humidity"],
        pressure=data["main"]["pressure"],
        wind_speed=round(data["wind"]["speed"], 1),
        wind_direction=data["wind"].get("deg", 0),
        description=data["weather"][0]["description"],
        cloudiness=data["clouds"]["all"],
        visibility=data.get("visibility", 10000),
        recorded_at=datetime.now(UTC).replace(
            minute=0, second=0, microsecond=0, tzinfo=None
        ),
    )


def generate_historical_reading(
    city_id: int,
    current_temp: float,
    recorded_at: datetime,
) -> WeatherReading:
    """
    Generates a plausible historical reading anchored to the city's
    real current temperature.

    Rather than using arbitrary temperature ranges, we derive historical
    values from the real current temperature. This means the generated
    history is consistent with what OpenWeatherMap actually returned —
    a city that is currently 34°C will have a warm history, not a cold one.

    Variation of +/- 6 degrees across 30 days is realistic for most
    cities outside of extreme seasonal transitions.
    """
    hour = recorded_at.hour
    # Temperature curve: warmer in the afternoon, cooler at night
    hour_factor = 0.5 + 0.5 * ((hour - 4) % 24) / 24
    temp_variation = random.uniform(-6, 6)
    temperature = round(current_temp + temp_variation * hour_factor, 1)
    feels_like = round(temperature - random.uniform(0, 3), 1)

    return WeatherReading(
        city_id=city_id,
        temperature=temperature,
        feels_like=feels_like,
        humidity=random.randint(40, 90),
        pressure=random.randint(1005, 1025),
        wind_speed=round(random.uniform(0.5, 12.0), 1),
        wind_direction=random.randint(0, 359),
        description=random.choice(WEATHER_CONDITIONS),
        cloudiness=random.randint(0, 100),
        visibility=random.randint(5000, 10000),
        recorded_at=recorded_at,
    )


def seed(db: Session) -> None:
    """
    Seeds the database with 21 cities and 30 days of weather data.

    For each city:
    1. Fetch real current conditions from OpenWeatherMap
    2. Store the real current reading as the most recent data point
    3. Generate 29 days of hourly history anchored to the real temperature

    Total: 21 cities x (1 real + 696 generated) = 14,637 readings.

    The check for existing data prevents duplicate seeding.
    """
    existing = db.query(City).count()
    if existing > 0:
        logger.info("Database already seeded. Skipping.")
        return

    logger.info("Seeding %d cities.", len(CITIES))
    city_objects = []
    for city_data in CITIES:
        city = City(**city_data)
        db.add(city)
        city_objects.append(city)

    db.commit()

    for city in city_objects:
        db.refresh(city)

    logger.info("Fetching real current weather and generating 30 days of history.")
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0, tzinfo=None)

    for city_obj, city_data in zip(city_objects, CITIES):
        readings = []

        # Fetch real current conditions
        raw = fetch_current_weather(city_data["latitude"], city_data["longitude"])

        if raw:
            current_reading = parse_current_weather(raw, city_obj.id)
            current_temp = current_reading.temperature
            logger.info("%-20s %.1f°C — real data fetched", city_obj.name, current_temp)
        else:
            # Fallback: generate current reading if API failed
            current_temp = random.uniform(15, 30)
            current_reading = generate_historical_reading(
                city_obj.id, current_temp, now
            )
            logger.warning(
                "%-20s API unavailable — using generated data.", city_obj.name
            )

        # Generate 29 days of hourly history (most recent hour excluded,
        # that is covered by the real current reading above)
        for hours_ago in range(29 * 24, 0, -1):
            recorded_at = now - timedelta(hours=hours_ago)
            reading = generate_historical_reading(
                city_obj.id, current_temp, recorded_at
            )
            readings.append(reading)

        # Add current reading as the final (most recent) data point
        readings.append(current_reading)

        db.add_all(readings)
        db.commit()

    total = len(city_objects) * 29 * 24 + len(city_objects)
    logger.info(
        "Seeding complete — %d cities, %d total readings. "
        "Current conditions from OpenWeatherMap, history anchored to real temperatures.",
        len(city_objects),
        total,
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()
