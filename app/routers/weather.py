from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.middleware.auth import require_api_key
from app.schemas.weather import (
    CityResponse,
    WeatherReadingResponse,
    WeatherStatsResponse,
    PaginatedWeatherResponse,
)
from app.services import weather as weather_service

router = APIRouter()


@router.get(
    "/cities",
    response_model=list[CityResponse],
    summary="List all cities",
    description="Returns all 21 cities tracked by the API, ordered alphabetically.",
)
def list_cities(
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
) -> list[CityResponse]:
    """
    The underscore _ for the api_key parameter is a Python convention
    meaning 'this value is required but not used in the function body'.
    The dependency runs and validates the key — we just don't need
    the key value itself inside the function.
    """
    return weather_service.get_all_cities(db)


@router.get(
    "/weather/latest",
    response_model=list[WeatherReadingResponse],
    summary="Latest readings for all cities",
    description="Returns the most recent weather reading for every tracked city. Optionally filter by continent.",
)
def get_latest_all(
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
    continent: str | None = Query(
        default=None,
        description="Filter results to a single continent, e.g. 'Africa', 'Europe', 'Asia'. Case-insensitive.",
    ),
) -> list[WeatherReadingResponse]:
    return weather_service.get_latest_readings_all_cities(db, continent=continent)


@router.get(
    "/weather/{city_name}/latest",
    response_model=WeatherReadingResponse,
    summary="Latest reading for a city",
    description="Returns the most recent weather reading for the specified city.",
)
def get_latest_for_city(
    city_name: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
) -> WeatherReadingResponse:
    city = weather_service.get_city_by_name(db, city_name)
    reading = weather_service.get_latest_reading_for_city(db, city)
    return reading


@router.get(
    "/weather/{city_name}/history",
    response_model=PaginatedWeatherResponse,
    summary="Historical readings for a city",
    description="Returns paginated weather history for the specified city, newest first.",
)
def get_city_history(
    city_name: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
    page: int = Query(default=1, ge=1, description="Page number, starting at 1"),
    limit: int = Query(
        default=20, ge=1, le=100, description="Records per page, maximum 100"
    ),
) -> PaginatedWeatherResponse:
    """
    Query parameters with validation baked in:
    - page must be >= 1 (ge=1 means 'greater than or equal to 1')
    - limit must be between 1 and 100 (ge=1, le=100)

    FastAPI validates these automatically and returns a 422 with a clear
    error message if a consumer sends page=0 or limit=500 — no manual
    validation code needed.
    """
    city = weather_service.get_city_by_name(db, city_name)
    readings, total_count = weather_service.get_city_history(db, city, page, limit)
    total_pages = -(-total_count // limit)  # ceiling division without math.ceil

    return PaginatedWeatherResponse(
        data=readings,
        total_count=total_count,
        page=page,
        limit=limit,
        total_pages=total_pages,
    )


@router.get(
    "/weather/{city_name}/stats",
    response_model=WeatherStatsResponse,
    summary="Weather statistics for a city",
    description="Returns aggregated min, max and average statistics over a requested number of days (1-30).",
)
def get_city_stats(
    city_name: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
    days: int = Query(
        default=7, ge=1, le=30, description="Number of days to include, maximum 30"
    ),
) -> WeatherStatsResponse:
    city = weather_service.get_city_by_name(db, city_name)
    return weather_service.get_city_stats(db, city, days)
