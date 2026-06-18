from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    pydantic-settings automatically reads from the .env file and
    validates every value at startup. If a required variable is missing,
    the app refuses to start — you catch configuration errors immediately,
    not at runtime when a request fails.
    """

    # Database
    database_url: str

    # Security
    api_key_secret: str

    # App
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Rate limiting
    rate_limit_per_minute: int = 60

    # OpenWeatherMap
    openweather_api_key: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Single instance shared across the entire app.
# Imported as: from app.config import settings
settings = Settings()
