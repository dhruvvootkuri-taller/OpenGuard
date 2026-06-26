.PHONY: install dev test lint format run worker agent frontend

install:
	pip install -r requirements-dev.txt

run:
	uvicorn src.main:app --reload

worker:
	celery -A src.worker:celery_app worker --loglevel=info

agent:
	python -m src.interfaces.cli.run_agent --camera-id front-door --source 0

test:
	pytest

lint:
	ruff check src tests

format:
	black src tests
	ruff check --fix src tests

frontend:
	cd frontend && npm run dev
