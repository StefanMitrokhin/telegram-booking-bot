.PHONY: install format lint test run seed

install:
	pip install -e ".[dev]"

format:
	ruff format .
	ruff check --fix .

lint:
	ruff check .
	ruff format --check .

test:
	pytest

run:
	python -m booking_bot

seed:
	python -m booking_bot.seed