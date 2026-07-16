from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.limiter import limiter
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
@limiter.limit("60/minute")
async def list_cities(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
) -> list[CityResponse]:
    return await weather_service.get_all_cities(db)


@router.get(
    "/weather/latest",
    response_model=list[WeatherReadingResponse],
    summary="Latest readings for all cities",
    description="Returns the most recent weather reading for every tracked city. Optionally filter by continent.",
)
@limiter.limit("60/minute")
async def get_latest_all(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
    continent: str | None = Query(
        default=None,
        description="Filter results to a single continent, e.g. 'Africa', 'Europe', 'Asia'. Case-insensitive.",
    ),
) -> list[WeatherReadingResponse]:
    return await weather_service.get_latest_readings_all_cities(db, continent=continent)


@router.get(
    "/weather/{city_name}/stats",
    response_model=WeatherStatsResponse,
    summary="Weather statistics for a city",
    description="Returns aggregated min, max and average statistics over a requested number of days (1-30).",
)
@limiter.limit("60/minute")
async def get_city_stats(
    request: Request,
    city_name: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
    days: int = Query(
        default=7, ge=1, le=30, description="Number of days to include, maximum 30"
    ),
) -> WeatherStatsResponse:
    city = await weather_service.get_city_by_name(db, city_name)
    return await weather_service.get_city_stats(db, city, days)


@router.get(
    "/weather/{city_name}/latest",
    response_model=WeatherReadingResponse,
    summary="Latest reading for a city",
    description="Returns the most recent weather reading for the specified city.",
)
@limiter.limit("60/minute")
async def get_latest_for_city(
    request: Request,
    city_name: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
) -> WeatherReadingResponse:
    city = await weather_service.get_city_by_name(db, city_name)
    reading = await weather_service.get_latest_reading_for_city(db, city)
    return reading


@router.get(
    "/weather/{city_name}/history",
    response_model=PaginatedWeatherResponse,
    summary="Historical readings for a city",
    description="Returns paginated weather history for the specified city, newest first.",
)
@limiter.limit("60/minute")
async def get_city_history(
    request: Request,
    city_name: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
    page: int = Query(default=1, ge=1, description="Page number, starting at 1"),
    limit: int = Query(
        default=20, ge=1, le=100, description="Records per page, maximum 100"
    ),
) -> PaginatedWeatherResponse:
    city = await weather_service.get_city_by_name(db, city_name)
    readings, total_count = await weather_service.get_city_history(
        db, city, page, limit
    )
    total_pages = -(-total_count // limit)  # ceiling division without math.ceil

    return PaginatedWeatherResponse(
        data=readings,
        total_count=total_count,
        page=page,
        limit=limit,
        total_pages=total_pages,
    )
