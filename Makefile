.PHONY: up down seed test lint format

up:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

down:
	docker stop weather-api-db && docker rm weather-api-db

seed:
	python -m app.seed.seed

test:
	python -m pytest tests/ -v

lint:
	python -m black --check app/ tests/

format:
	python -m black app/ tests/