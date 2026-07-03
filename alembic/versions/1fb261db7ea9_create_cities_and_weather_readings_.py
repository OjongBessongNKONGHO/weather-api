"""create cities and weather readings tables

Revision ID: 1fb261db7ea9
Revises:
Create Date: 2026-07-03

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# Revision identifiers used by Alembic to track migration history.
revision: str = "1fb261db7ea9"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create the initial schema — cities and weather_readings tables.

    cities is created first because weather_readings references it
    via a foreign key on city_id. PostgreSQL enforces referential
    integrity at the DDL level — the referenced table must exist
    before the referencing table is created.
    """

    # --- cities table ---
    op.create_table(
        "cities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("country", sa.String(100), nullable=False),
        sa.Column("continent", sa.String(50), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("timezone", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # Unique constraint — city names must be unique across the table.
    op.create_unique_constraint("uq_cities_name", "cities", ["name"])

    # Index on name for fast city lookups by name.
    op.create_index("ix_cities_name", "cities", ["name"], unique=True)
    op.create_index("ix_cities_id", "cities", ["id"])

    # --- weather_readings table ---
    op.create_table(
        "weather_readings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("city_id", sa.Integer(), sa.ForeignKey("cities.id"), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=False),
        sa.Column("feels_like", sa.Float(), nullable=False),
        sa.Column("humidity", sa.Integer(), nullable=False),
        sa.Column("pressure", sa.Integer(), nullable=False),
        sa.Column("wind_speed", sa.Float(), nullable=False),
        sa.Column("wind_direction", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(200), nullable=False),
        sa.Column("cloudiness", sa.Integer(), nullable=False),
        sa.Column("visibility", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # Unique constraint — one reading per city per timestamp.
    # Prevents duplicate readings if the seeder or ingestion runs twice.
    op.create_unique_constraint(
        "uq_city_reading_time",
        "weather_readings",
        ["city_id", "recorded_at"],
    )

    # Index on city_id for fast city-based filtering.
    op.create_index("ix_weather_readings_id", "weather_readings", ["id"])
    op.create_index(
        "ix_weather_readings_city_id", "weather_readings", ["city_id"]
    )

    # Index on recorded_at for fast time-range queries.
    op.create_index(
        "ix_weather_readings_recorded_at", "weather_readings", ["recorded_at"]
    )

    # Composite index for the most common query pattern:
    # "give me readings for city X ordered by time."
    # Without this, PostgreSQL scans every row in the table.
    op.create_index(
        "ix_weather_readings_city_recorded",
        "weather_readings",
        ["city_id", "recorded_at"],
    )


def downgrade() -> None:
    """
    Drop all tables created in upgrade() in reverse order.

    weather_readings must be dropped before cities because it holds
    a foreign key reference to cities. Dropping cities first would
    violate referential integrity and PostgreSQL would reject it.
    """
    op.drop_table("weather_readings")
    op.drop_table("cities")