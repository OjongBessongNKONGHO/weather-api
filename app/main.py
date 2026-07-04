from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.limiter import limiter
from app.config import settings
from app.database import get_db
from app.middleware.logging import RequestLoggingMiddleware
from app.routers import weather, health
from app.logging_config import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    yield
    """
    Code that runs once at startup and once at shutdown.
    The asynccontextmanager pattern replaced the older @app.on_event
    approach in modern FastAPI. Everything before 'yield' runs on
    startup, everything after runs on shutdown.

    Schema management is handled by Alembic migrations — not create_all.
    Running create_all in production is dangerous because it cannot
    handle schema evolution: adding a column, changing a type, or adding
    an index requires a versioned migration script, not a blunt create_all
    that silently does nothing if the table already exists.

    To apply migrations: alembic upgrade head
    To create a new migration: alembic revision -m "description"
    """
    yield


app = FastAPI(
    title="Weather API",
    description=(
        "REST API serving real-time and historical weather data "
        "for 21 cities across 6 continents. "
        "All endpoints require an X-API-Key header."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Rate limiting — attaches the limiter to the app so slowapi
# can intercept requests and enforce per-IP limits.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(RequestLoggingMiddleware)

# CORS — controls which origins can call this API from a browser.
# In development we allow all origins. In production you would
# restrict this to your frontend domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_env == "development" else [],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """
    Custom 404 handler that returns a helpful message instead of
    FastAPI's default plain text response.
    """
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "detail": "Endpoint not found.",
            "docs": str(request.base_url) + "docs",
        },
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """
    Catches unhandled exceptions and returns a clean JSON response
    instead of exposing stack traces to API consumers.
    """
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal error occurred. Please try again later."},
    )


# Register routers under the /api/v1 prefix.
# Versioning the API from day one means you can introduce /api/v2
# later without breaking existing consumers — they keep calling /api/v1
# until they choose to migrate.
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(weather.router, prefix="/api/v1", tags=["Weather"])
